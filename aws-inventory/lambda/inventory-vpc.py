import boto3
from botocore.exceptions import ClientError
import json
import os
import time
from datetime import datetime, timezone
from dateutil import tz

from antiope.aws_account import *
from common import *

import logging
logger = logging.getLogger()
logger.setLevel(getattr(logging, os.getenv('LOG_LEVEL', default='INFO')))
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

RESOURCE_PATH = "ec2/vpc"


def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        for r in target_account.get_regions():
            try:
                discover_vpcs(target_account, r)
            except ClientError as e:
                # Move onto next region if we get access denied. This is probably SCPs
                if e.response['Error']['Code'] == 'AccessDeniedException':
                    logger.error(f"AccessDeniedException for region {r} in function {context.function_name} for {target_account.account_name}({target_account.account_id})")
                    continue
                else:
                    raise  # pass on to the next handlier

    except AntiopeAssumeRoleError as e:
        logger.error("Unable to assume role into account {}({})".format(target_account.account_name, target_account.account_id))
        return()
    except ClientError as e:
        if e.response['Error']['Code'] == 'UnauthorizedOperation':
            logger.error("Antiope doesn't have proper permissions to this account")
            return(event)
        logger.critical("AWS Error getting info for {}: {}".format(message['account_id'], e))
        capture_error(message, context, e, "ClientError for {}: {}".format(message['account_id'], e))
        raise
    except Exception as e:
        logger.critical("{}\nMessage: {}\nContext: {}".format(e, message, vars(context)))
        capture_error(message, context, e, "General Exception for {}: {}".format(message['account_id'], e))
        raise


def discover_vpcs(target_account, region):
    '''Iterate across all regions to discover VPCs'''

    dynamodb = boto3.resource('dynamodb')
    vpc_table  = dynamodb.Table(os.environ['VPC_TABLE'])
    ec2_client = target_account.get_client('ec2', region=region)
    response = ec2_client.describe_vpcs()

    # Only ask for the VIFs once, and store them in a dict by vgw_id
    dx_vifs, dx_gw_assoc = discover_all_dx_vifs(ec2_client, region, target_account)

    # Same with the VPC peers.
    vpc_peers = discover_vpc_peering(ec2_client)

    resource_item = {}
    resource_item['awsAccountId']                   = target_account.account_id
    resource_item['awsAccountName']                 = target_account.account_name
    resource_item['resourceType']                   = "AWS::EC2::VPC"
    resource_item['source']                         = "Antiope"
    resource_item['awsRegion']                      = region

    for v in response['Vpcs']:

        resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
        resource_item['configuration']                  = v

        resource_item['supplementaryConfiguration']     = {}
        resource_item['resourceId']                     = v['VpcId']
        resource_item['errors']                         = {}

        # We also save the VPCs to a DDB Table
        ddb_item = {
            'vpc_id':               v['VpcId'],
            'account_id':           str(target_account.account_id),
            'region':               region,
            'cidr_block':           v['CidrBlock'],
            'default':              v['IsDefault'],
            'last_seen':            str(datetime.datetime.now())
        }

        if 'Tags' in v:
            resource_item['tags']                       = parse_tags(v['Tags'])
            ddb_item['tags']                            = resource_item['tags']
            if 'Name' in ddb_item['tags']:
                ddb_item['name']                        = ddb_item['tags']['Name']
                resource_item['resourceName']           = resource_item['tags']['Name']

        vgw = discover_vgw(ec2_client, v['VpcId'])
        if vgw is not None:
            resource_item['supplementaryConfiguration']['VpnGateways'] = vgw
            vgw_id = vgw['VpnGatewayId']
            ddb_item['vgw_id'] = vgw['VpnGatewayId']

            vpn = discover_vpn(ec2_client, vgw_id)
            if vpn is not None:
                resource_item['supplementaryConfiguration']['VpnConnections'] = vpn

            if vgw_id in dx_vifs:
                resource_item['supplementaryConfiguration']['DXVirtualInterfaces'] = dx_vifs[vgw_id]

            if vgw_id in dx_gw_assoc:
                resource_item['supplementaryConfiguration']['directConnectGatewayAssociations'] = dx_gw_assoc[vgw_id]

        # VPC Peering connections are not dependent on a VGW
        if v['VpcId'] in vpc_peers:
            resource_item['supplementaryConfiguration']['VpcPeeringConnections'] = vpc_peers[v['VpcId']]

        # We should cache the VPC Instance count in DDB
        ddb_item['instance_states'] = query_instances(ec2_client, v['VpcId'])

        save_resource_to_s3(RESOURCE_PATH, resource_item['resourceId'], resource_item)
        logger.info("Discovered VPC ({}) in {}\nData: {}".format(v['VpcId'], target_account.account_id, json.dumps(ddb_item, sort_keys=True)))
        try:
            response = vpc_table.put_item(Item=ddb_item)
        except ClientError as e:
            logger.error("Unable to save VPC ({}) in {}: {}\nData: {}".format(v['VpcId'], target_account.account_id, e, json.dumps(ddb_item, sort_keys=True)))


def discover_vgw(ec2_client, vpc_id):
    '''find the vgw if it exists for this VPC '''
    try:
        response = ec2_client.describe_vpn_gateways(
            Filters=[{'Name': 'attachment.vpc-id', 'Values': [vpc_id]}]
        )

        return(response['VpnGateways'][0])
    except KeyError:
        return(None)
    except IndexError:
        return(None)
    except ClientError as e:
        logger.error("Unable to get vgw for {}: {}".format(vpc_id, e))
        return(None)


def discover_vpn(ec2_client, vgw_id):
    '''Given the vgw_id, returns a list of active VPN connections to this VPC'''
    vpn_response = ec2_client.describe_vpn_connections(
        Filters=[
            {
                'Name': 'vpn-gateway-id',
                'Values': [vgw_id]
            },
        ]
    )
    if 'VpnConnections' in vpn_response:
        return(vpn_response['VpnConnections'])


def discover_all_dx_vifs(ec2_client, region, target_account):
    '''returns any dx VIFs (virtual interfaces), indexed by the vgw_id'''

    output = {}
    assoc_output = {}

    try:  # Not all regions support DX
        dx_client = target_account.get_client('directconnect', region=region)

        # This call can't filter on a VGW, so we need to iterate
        # Also this call doesn't paginate
        response = dx_client.describe_virtual_interfaces()
        for vif in response['virtualInterfaces']:
            if vif['ownerAccount'] != target_account.account_id:
                # You must be in an account that is hosting VIFs. We deal with that in a different modules
                continue

            if vif['directConnectGatewayId']:
                associations = get_all_dx_gw_associations(dx_client, vif['directConnectGatewayId'])
                for vgw_id, assoc in associations.items():
                    if vgw_id not in output:
                        output[vgw_id] = []
                    output[vgw_id].append(vif)

                    if vgw_id not in assoc_output:
                        assoc_output[vgw_id] = []
                    assoc_output[vgw_id].append(assoc)

            else:  # This VIF is directly attached to the VGW.
                # There can be multiple VIFs per VGW, so this needs to be a list
                if vif['virtualGatewayId'] not in output:
                    output[vif['virtualGatewayId']] = []
                output[vif['virtualGatewayId']].append(vif)

        return(output, assoc_output)
    except Exception as e:
        logger.error("Got an exception trying to dx_client.describe_virtual_interfaces() : {}".format(e))
        raise  # raise the roof till we know how to handle.


def get_all_dx_gw_associations(dx_client, dxgw_id):
    '''Return all the VGW Associations for a specific DirectConnect Gateway.'''

    associations = []

    dx_gw_response = dx_client.describe_direct_connect_gateway_associations(directConnectGatewayId=dxgw_id)
    while 'nextToken' in dx_gw_response:
        associations += dx_gw_response['directConnectGatewayAssociations']
        dx_gw_response = dx_client.describe_direct_connect_gateway_associations(directConnectGatewayId=dxgw_id, nextToken=dx_gw_response['nextToken'])

    associations += dx_gw_response['directConnectGatewayAssociations']

    print(associations)

    # all I need are the VGWs
    output = {}
    for a in associations:
        if 'virtualGatewayId' not in a:
            logger.error(f"No virtualGatewayId for DX GW Association: {a}")
        else:
            output[a['virtualGatewayId']] = a
    return(output)


def discover_vpc_peering(ec2_client):
    '''return a list of all the VPC peers, as a dict of arrays, indexed by vpc_id'''

    output = {}
    response = ec2_client.describe_vpc_peering_connections()

    for px in response['VpcPeeringConnections']:
        if px['AccepterVpcInfo']['VpcId'] not in output:
            output[px['AccepterVpcInfo']['VpcId']] = []
        output[px['AccepterVpcInfo']['VpcId']].append(px)

        if px['RequesterVpcInfo']['VpcId'] not in output:
            output[px['RequesterVpcInfo']['VpcId']] = []
        output[px['RequesterVpcInfo']['VpcId']].append(px)

    return(output)


def query_instances(ec2_client, vpc_id, instance_state = None):
    '''return an array of dict representing the data from describe_instances()'''

    state_count = {
        "pending": 0,
        "running": 0,
        "shutting-down": 0,
        "terminated": 0,
        "stopping": 0,
        "stopped": 0
    }

    filters = [{'Name': 'vpc-id', 'Values': [vpc_id]}]
    if instance_state is not None:
        filters.append({'Name': 'instance-state-name', 'Values': [instance_state]})

    response = ec2_client.describe_instances(
        Filters = filters,
        MaxResults = 1000
    )
    while 'NextToken' in response:
        for r in response['Reservations']:
            for i in r['Instances']:
                state = i['State']['Name']
                state_count[state] += 1
        response = ec2_client.describe_instances(
            Filters = filters,
            MaxResults = 1000,
            NextToken = response['NextToken']
        )
    # Done with the while loop (or never entered it) do the last batch
    for r in response['Reservations']:
        for i in r['Instances']:
            state = i['State']['Name']
            state_count[state] += 1
    return(state_count)
