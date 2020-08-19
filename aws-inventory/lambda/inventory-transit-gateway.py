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

RESOURCE_PATH = "ec2/transitgateway"


def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
            
        for r in target_account.get_regions():
            try:
                discover_transit_gateways(target_account, r)
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

def discover_transit_gateways(target_account, region):
    '''Iterate accross all regions to discover transit gateways'''
    
    ec2_client = target_account.get_client('ec2', region=region)
    response = ec2_client.describe_transit_gateways()

    if response['TransitGateways']:
    
        for tg in response['TransitGateways']:
        
            resource_item = {}
            resource_item['awsAccountId']                   = target_account.account_id
            resource_item['awsAccountName']                 = target_account.account_name
            resource_item['resourceType']                   = "AWS::EC2::TransitGateway"
            resource_item['source']                         = "Antiope"
            resource_item['awsRegion']                      = region
            resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
            resource_item['configuration']                  = tg
            resource_item['supplementaryConfiguration']     = {}
            resource_item['resourceId']                     = tg['TransitGatewayId']
            resource_item['ARN']                            = tg['TransitGatewayArn']
            resource_item['resourceCreationTime']           = tg['CreationTime']
            resource_item['errors']                         = {}
            
            if 'Tags' in tg:
                resource_item['tags']                       = parse_tags(tg['Tags'])
    
            # Get the transit gateway attachements based on the gateway ID and add it as part of the supplementray configuration
            attachements = discover_transit_gateway_attachments(ec2_client, tg['TransitGatewayId'])
            
            for a in attachements:
                
                resource_item['supplementaryConfiguration'] = a
                
                if a['ResourceType'] == 'tgw-peering':
                    tg_peering_response = discover_transit_gateway_peering_attachments(ec2_client, a['TransitGatewayId'], a['TransitGatewayAttachmentId'])[0]
                    resource_item['supplementaryConfiguration']['TransitGatewayPeeringAttachments'] = tg_peering_response
                
                if a['ResourceType'] == 'vpc':
                    vpc_attachments_response = discover_transit_gateway_vpc_attachments(ec2_client, a['TransitGatewayId'], a['ResourceId'])[0]
                    resource_item['supplementaryConfiguration']['TransitGatewayVpcAttachments'] = vpc_attachments_response
        
            # Save files to S3
            save_resource_to_s3(RESOURCE_PATH, tg['TransitGatewayId'], resource_item)
       
            logger.info("Discovered Transit Gateways ({}) in account {} for region {}".format(tg['TransitGatewayId'], target_account.account_id, region))
            logger.debug("Data: {}".format(resource_item))
    else:
        logger.debug("No Transit Gateways found for account {} in region {}".format(target_account.account_id, region))

def discover_transit_gateway_attachments(ec2_client, tgId):
    ''' Get transit gateway attachement based on transit gateway ID'''
    response = ec2_client.describe_transit_gateway_attachments(
            Filters=[
                {
                'Name': 'transit-gateway-id',
                'Values': [
                    tgId,
                ]
                },
            ]
        )
      
    return(response['TransitGatewayAttachments']) 
        
def discover_transit_gateway_vpc_attachments(ec2_client, tgId, resourceId):
    ''' Get transit gateway vpc attachement information based on transit gateway ID and vpc ID'''
    response = ec2_client.describe_transit_gateway_vpc_attachments(
        Filters=[
        {
            'Name': 'transit-gateway-id',
            'Values': [
                tgId,
            ],
            'Name': 'vpc-id',
            'Values': [
                resourceId,
            ]
        },
        ]    
    )

    return(response['TransitGatewayVpcAttachments'])

def discover_transit_gateway_peering_attachments(ec2_client, tgId, tgAttachId):
    '''Get Transit Gateway Peering Attachment configuration based on the Transit Gateway ID'''
    response = ec2_client.describe_transit_gateway_peering_attachments(
        Filters=[
            {
                'Name': 'transit-gateway-id',
                'Values': [
                    tgId,
                ],
                'Name': 'transit-gateway-attachment-id',
                'Values': [
                    tgAttachId,
                ]
            },
        ]
    )
    
    return(response['TransitGatewayPeeringAttachments'])