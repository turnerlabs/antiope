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

RESOURCE_PATH = "ec2/vpn"


def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
            
        for r in target_account.get_regions():
                
            try:
                discover_client_vpn_endpoints(target_account, r)
            except ClientError as e:
                # Move onto next region if we get access denied. This is probably SCPs
                if e.response['Error']['Code'] == 'AccessDeniedException':
                    logger.error(f"AccessDeniedException for region {r} in function {context.function_name} for {target_account.account_name}({target_account.account_id})")
                    continue
                elif e.response['Error']['Code'] == 'UnauthorizedOperation':
                    logger.error(f"UnauthorizedOperation for region {r} in function {context.function_name} for {target_account.account_name}({target_account.account_id})")
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
        #capture_error(message, context, e, "ClientError for {}: {}".format(message['account_id'], e))
        raise
    
    except Exception as e:
        logger.critical("{}\nMessage: {}\nContext: {}".format(e, message, vars(context)))
        #capture_error(message, context, e, "General Exception for {}: {}".format(message['account_id'], e))
        raise

def discover_client_vpn_endpoints(target_account, region):
    '''Iterate accross all regions to discover client vpn endpoints'''
    
    ec2_client = target_account.get_client('ec2', region=region)
    response = ec2_client.describe_client_vpn_endpoints()
    
    if response['ClientVpnEndpoints']:
        
        for cpvn in response['ClientVpnEndpoints']:
            
            resource_item = {}
            resource_item['awsAccountId']                   = target_account.account_id
            resource_item['awsAccountName']                 = target_account.account_name
            resource_item['resourceType']                   = "AWS::EC2::ClientVpnEndpoints"
            resource_item['source']                         = "Antiope"
            resource_item['awsRegion']                      = region
            resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
            resource_item['configuration']                  = cpvn
            resource_item['supplementaryConfiguration']     = {}
            resource_item['resourceId']                     = cvpn['ClientVpnEndpointId']
            resource_item['resourceCreationTime']           = cpvn['Timestamp']
            resource_item['errors']                         = {}
        
            # Get the VPN connection configuration and add as part of the supplmentry configuration.
            connections = discover_client_vpn_connections(ec2_client, cvpn['ClientVpnEndpointId'])
        
            for e in endpoints:
                resource_item['supplementaryConfiguration'] = e
    
            # Save files to S3
            #save_resource_to_s3(RESOURCE_PATH, cvpn['ClientVpnEndpointId'], resource_item)
       
            logger.info("Discovered Client VPN connection ({}) in account {} for region {}".format(cpvn['ClientVpnEndpointId'], target_account.account_id, region))
            logger.debug("Data: {}".format(resource_item))
    else:
        logger.debug("No Client VPN connections found for account {} in region {}".format(target_account.account_id, region))
    
def discover_client_vpn_connections(ec2_client, vpnId):
    '''Get client VPN endpoint configuration based on the endpointId'''
    
    response = ec2_client.describe_client_vpn_connections(
            Filters=[
                {
                    'Name': 'ClientVpnEndpointId',
                    'Values': [
                            vpnId,
                    ]
                },
            ]
        
        )
    
    return(response['Connections'])