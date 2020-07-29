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
                discover_transit_gateway_attachments(target_account, r)
            except ClientError as e:
                # Move onto next region if we get access denied. This is probably SCPs
                if e.response['Error']['Code'] == 'AccessDeniedException':
                    logger.error(f"AccessDeniedException for region {r} in function {context.function_name} for {target_account.account_name}({target_account.account_id})")
                    continue
                else:
                    raise  # pass on to the next handler

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

def discover_transit_gateway_attachments(target_account, region):
    '''Iterate across all regions to discover transit gateways'''
    
    ec2_client = target_account.get_client('ec2', region=region)
    response = ec2_client.describe_transit_gateway_attachments()
    
    if response['TransitGatewayAttachments']:
        resource_item = {}
        resource_item['awsAccountId']                   = target_account.account_id
        resource_item['awsAccountName']                 = target_account.account_name
        resource_item['resourceType']                   = "AWS::EC2::TransitGateway"
        resource_item['source']                         = "Antiope"
        resource_item['awsRegion']                      = region

        for tg in response['TransitGatewayAttachments']:
        
            resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
            resource_item['configuration']                  = tg
            resource_item['supplementaryConfiguration']     = {}
            resource_item['resourceId']                     = tg['ResourceId']
            resource_item['errors']                         = {}

            if 'Tags' in tg:
                resource_item['tags']                       = parse_tags(tg['Tags'])

            if tg['ResourceType'] == 'vpn':
                vpn_response = discover_transit_gateway_vpn(ec2_client, tg['TransitGatewayId'], tg['ResourceId'])[0]
                
                # We don't need this for the purpose of inventory discovery.
                del vpn_response['CustomerGatewayConfiguration']
                
                resource_item['supplementaryConfiguration']['VpnConnections'] = vpn_response
                
            save_resource_to_s3(RESOURCE_PATH, resource_item['resourceId'], resource_item)
            
            logger.info("Discovered Transit Gateways ({}) in account {} for region {}\n".format(resource_item['resourceId'], target_account.account_id, region))
            logger.debug("Data: {}".format(resource_item))
    else:
        logger.debug("No Transit Gateways found for account {} in region {}".format(target_account.account_id, region))

def discover_transit_gateway_vpn(ec2_client, tg_id, vpn_id):
    '''Get VPN Configuration based on the Transit Gateway ID'''
    response = ec2_client.describe_vpn_connections(
        Filters=[
            {
                'Name': 'transit-gateway-id',
                'Values': [
                    tg_id,
                ],
                'Name': 'vpn-connection-id',
                'Values': [
                    vpn_id,
                ]
            },
        ]
    )
    
    return(response['VpnConnections'])