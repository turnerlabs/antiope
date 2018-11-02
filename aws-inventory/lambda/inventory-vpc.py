
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

    for v in response['Vpcs']:

        # Get the VGW ID if there is one and add as an attribute of the DDB item
        try:
            response = ec2_client.describe_vpn_gateways(
                Filters=[
                    {
                        'Name': 'attachment.vpc-id',
                        'Values': [v['VpcId']]
                    }
                ]
            )

            v['VpnGateway'] = response['VpnGateways'][0]
            v['VpnGatewayId'] = v['VpnGateway']['VpnGatewayId']
        except KeyError:
            v['VpnGatewayId'] = None
        except IndexError:
            v['VpnGatewayId'] = None
        except ClientError as e:
            v['VpnGatewayId'] = None
            logger.error("Unable to get vgw for {}: {}".format(v['VpcId'], e))

        # FIXME. Get all the other VPC attribs that might not be in the describe_vpcs() call
        # I'm thinking, VPC Endpoints, VPC Peering, VPC Privatelink (which is endpoints)
        # Also VPN & DX might need to be here.

        # Save all VPCs!
        v['resource_type']    = "ec2-vpc"
        v['account_id']       = target_account.account_id
        v['account_name']     = target_account.account_name
        save_resource_to_s3(RESOURCE_PATH, v['VpcId'], v)

        item = {
                    'vpc_id':               v['VpcId'],
                    'account_id':           str(target_account.account_id),
                    'region':               region,
                    'cidr_block':           v['CidrBlock'],
                    'default':              v['IsDefault']
                }

        if 'VpnGateway' in v:
            item['vgw'] = v['VpnGateway']

        if 'Tags' in v:
            # Parse the tags to make them more searchable in the DDB Table
            item['tags'] = parse_tags(v['Tags'])
            if 'Name' in item['tags']:
                item['name'] = item['tags']['Name']

        if v['VpnGatewayId'] is not None:
            item['vgw_id'] = v['VpnGatewayId']

        logger.info("Discovered VPC ({}) in {}\nData: {}".format(v['VpcId'], target_account.account_id, json.dumps(item, sort_keys=True)))

        try:
            response = vpc_table.put_item(Item=item)
        except ClientError as e:
            logger.error("Unable to save VPC ({}) in {}: {}\nData: {}".format(v['VpcId'], target_account.account_id, e, json.dumps(item, sort_keys=True)))



def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))