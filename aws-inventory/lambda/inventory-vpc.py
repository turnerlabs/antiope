
import boto3
from botocore.exceptions import ClientError

import json
import os
import time
import datetime
from dateutil import tz

from lib.account import *
from lib.common import *

import logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)

RESOURCE_PATH = "ec2/vpc"

def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        for r in target_account.get_regions():
            discover_vpcs(target_account, r)

    except AssumeRoleError as e:
        logger.error("Unable to assume role into account {}({})".format(target_account.account_name, target_account.account_id))
        return()
    except ClientError as e:
        logger.error("AWS Error getting info for {}: {}".format(target_account.account_name, e))
        return()
    except Exception as e:
        logger.error("{}\nMessage: {}\nContext: {}".format(e, message, vars(context)))
        raise

def discover_vpcs(target_account, region):
    '''Iterate across all regions to discover VPCs'''

    dynamodb = boto3.resource('dynamodb')
    vpc_table  = dynamodb.Table(os.environ['VPC_TABLE'])
    ec2_client = target_account.get_client('ec2', region=region)
    response = ec2_client.describe_vpcs()

    # Only ask for the VIFs once, and store them in a dict by vgw_id
    dx_vifs = discover_all_dx_vifs(ec2_client, region, target_account)

    resource_item = {}
    resource_item['awsAccountId']                   = target_account.account_id
    resource_item['awsAccountName']                 = target_account.account_name
    resource_item['resourceType']                   = "AWS::EC2::VPC"
    resource_item['source']                         = "Antiope"
    resource_item['awsRegion']                      = region

    for v in response['Vpcs']:

        resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now(tz.gettz('US/Eastern')))
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
                    'last_seen':            str(datetime.datetime.now(tz.gettz('US/Eastern')))
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

        # VPC Peering connections are not dependent on a VGW
        peer_list = discover_vpc_peering(ec2_client, v['VpcId'])
        if peer_list is not None:
            resource_item['supplementaryConfiguration']['VpcPeeringConnections'] = peer_list


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
            Filters=[{'Name': 'attachment.vpc-id', 'Values': [vpc_id] } ]
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

    try: # Not all regions support DX
        dx_client = target_account.get_client('directconnect', region=region)

        # This call can't filter on a VGW, so we need to iterate
        # Also this call doesn't paginate
        response = dx_client.describe_virtual_interfaces()
        for vif in response['virtualInterfaces']:
            if vif['ownerAccount'] != target_account.account_id:
                # You must be in an account that is hosting VIFs. We deal with that in a different modules
                continue

            # There can be multiple VIFs per VGW, so this needs to be a list
            if vif['virtualGatewayId'] not in output:
                output[vif['virtualGatewayId']] = []

            output[vif['virtualGatewayId']].append(vif)

        return(output)
    except Exception as e:
        logger.error("Got an exception trying to dx_client.describe_virtual_interfaces() : {}".format(e))
        raise # raise the roof till we know how to handle.


def discover_vpc_peering(ec2_client, vpc_id):
    response = ec2_client.describe_vpc_peering_connections(
        Filters=[
            {
                'Name': 'accepter-vpc-info.vpc-id',
                'Values': [vpc_id]
            },
            {
                'Name': 'requester-vpc-info.vpc-id',
                'Values': [vpc_id]
            },
        ])
    if 'VpcPeeringConnections' in response:
        return(response['VpcPeeringConnections'])
    else:
        return(None)




# def json_serial(obj):
#     """JSON serializer for objects not serializable by default json code"""

#     if isinstance(obj, (datetime, date)):
#         return obj.isoformat()
#     raise TypeError ("Type %s not serializable" % type(obj))


