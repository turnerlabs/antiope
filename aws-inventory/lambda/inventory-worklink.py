import boto3
from botocore.exceptions import ClientError, EndpointConnectionError
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

RESOURCE_PATH = "worklink/fleet"


def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
                    
        target_account = AWSAccount(message['account_id'])
                
        for r in target_account.get_regions():
        
            try:
                discover_worklink_fleets(target_account, r)
    
            except ClientError as e:
                # Move onto next region if we get access denied. This is probably SCPs.
                if e.response['Error']['Code'] == 'AccessDeniedException':
                    logger.error(f"AccessDeniedException for region {r} in function {context.function_name} for {target_account.account_name}({target_account.account_id})")
                    continue
                else:
                    raise
        
            except EndpointConnectionError as e:
                # Move onto next region if we get an endpoint connection error.  This is probably due to the region not being supported.
                logger.error(f"EndpointConnectionError for region {r} in function {context.function_name} for {target_account.account_name}({target_account.account_id})")
                continue
       
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
    
def discover_worklink_fleets(target_account, region):
    '''Iterate accross all regions to discover worklink fleets'''
    
    worklink_client = target_account.get_client('worklink', region=region)
    response = worklink_client.list_fleets()
    
    if response['FleetSummaryList']:
        
        for fleet in response['FleetSummaryList']:

            resource_item = {}
            resource_item['awsAccountId']                   = target_account.account_id
            resource_item['awsAccountName']                 = target_account.account_name
            resource_item['resourceType']                   = "AWS::Worklink::Fleet"
            resource_item['source']                         = "Antiope"
            resource_item['awsRegion']                      = region
            resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
            resource_item['configuration']                  = fleet
            resource_item['supplementaryConfiguration']     = {}
            resource_item['resourceId']                     = f"fleet-{fleet['FleetName']}"
            resource_item['resourceCreationTime']           = fleet['CreatedTime']
            resource_item['Arn']                            = fleet['FleetArn']
            resource_item['errors']                         = {}
            
            if 'Tags' in fleet:
                resource_item['tags']                       = parse_tags(fleet['Tags'])
                
            # Obtain the domains configured as part of the fleet and add as part of the supplementary configuration.
            domains = discover_fleet_domains(worklink_client, fleet['FleetArn'])
            
            if domains:
                resource_item['supplementaryConfiguration']['Domains'] = domains
            
            # Obtain the devices configured as part of the fleet and add as part of the supplementary configuration.
            devices = discover_fleet_devices(worklink_client, fleet['FleetArn'])
            
            if devices:
                resource_item['supplementaryConfiguration']['Devices'] = devices
            
            # Obtain the website authorities configured as part of the fleet and add as part of the supplementary configuration.
            authorities = discover_fleet_certificate_authorities(worklink_client, fleet['FleetArn'])
            
            if authorities:
                resource_item['supplementaryConfiguration']['WebsiteCertificateAuthorities'] = authorities
            
            # Obtain the authorization providers configured as part of the fleet and add as part of the supplementary configuration.
            auth_providers = discover_fleet_authorization_providers(worklink_client, fleet['FleetArn'])
            
            if auth_providers:
                resource_item['supplementaryConfiguration']['WebsiteAuthorizationProviders'] = auth_providers
            
            # Save files to S3
            save_resource_to_s3(RESOURCE_PATH, resource_item['resourceId'], resource_item)
           
            logger.info("Discovered Worklink configuration ({}) in account {} for region {}".format(fleet['FleetName'], target_account.account_id, region))
            logger.debug("Data: {}".format(resource_item))

    else:
        logger.debug("No Worklink Fleets found for account {} in region {}".format(target_account.account_id, region))


def discover_fleet_domains(worklink_client, arn):
    
    items_list = worklink_client.list_domains(
        FleetArn=arn
    )
    
    if items_list['Domains']:
        
        details = {}
        
        for item in items_list['Domains']:
            
            data = worklink_client.describe_domain(
                FleetArn=arn,
                DomainName=item['DomainName']
            )
        
            details[item['DomainName']] = data
        
        return(details)
    
    else:
        return(items_list['Domains'])


def discover_fleet_devices(worklink_client, arn):
    
    # Obtain a list of devices
    items_list = worklink_client.list_devices(
        FleetArn=arn
    )
        
    # Obtain the device specific details
    if items_list['Devices']:
        
        details = {}
        
        for item in items_list['Devices']:
            
            data = worklink_client.describe_device(
                FleetArn=arn,
                DeviceId=item['DeviceId']
            )
                        
            details[item['DeviceId']] = data
        
        return(details)
    
    else:
        return(items_list['Devices'])


def discover_fleet_certificate_authorities(worklink_client, arn):
    
    items_list = worklink_client.list_website_certificate_authorities(
        FleetArn=arn
    )
        
    if items_list['WebsiteCertificateAuthorities']:

        details = {}

        for item in items_list['WebsiteCertificateAuthorities']:

            data = worklink_client.describe_website_certificate_authority(
                FleetArn=arn,
                WebsiteCaId=item['WebsiteCaId']
            )

            details[item['DisplayName']] = data
            details[item['DisplayName']]['WebsiteCaId'] = item['WebsiteCaId']

        return(details)

    else:
        return(items_list['WebsiteCertificateAuthorities'])


def discover_fleet_authorization_providers(worklink_client, arn):
    
    data = worklink_client.list_website_authorization_providers(
        FleetArn=arn
    )
    
    return(data['WebsiteAuthorizationProviders'])