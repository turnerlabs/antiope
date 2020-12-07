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

WAFv2_PATH = "wafv2/webacl"


def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        # Collect CLOUDFRONT WAFs from us-east-1
        discover_cloudfront_WAFs(target_account)
        # Now get the regional ones
        for r in target_account.get_regions():
            try:
                discover_regional_WAFs(target_account, r)
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


def discover_regional_WAFs(target_account, region):
    '''Find and process all the REGIONAL AWS WAFv2'''

    web_acls = []
    client = target_account.get_client('wafv2', region=region)
    response = client.list_web_acls(Scope='REGIONAL')
    while 'NextMarker' in response:  # Gotta Catch 'em all!
        web_acls += response['WebACLs']
        response = client.list_web_acls(Scope='REGIONAL', NextMarker=response['NextMarker'])
    web_acls += response['WebACLs']

    logger.debug(f"Discovered {len(web_acls)} WebACLs in {target_account.account_name}")

    for acl in web_acls:
        response = client.get_web_acl(Name=acl['Name'], Scope='REGIONAL', Id=acl['Id'])
        process_v2_acl(client, response['WebACL'], target_account, region)

def discover_cloudfront_WAFs(target_account):
    '''Find and process all the CLOUDFRONT AWS WAFv2 (via us-east-1)'''

    web_acls = []
    client = target_account.get_client('wafv2', region='us-east-1')
    response = client.list_web_acls(Scope='CLOUDFRONT')
    while 'NextMarker' in response:  # Gotta Catch 'em all!
        web_acls += response['WebACLs']
        response = client.list_web_acls(Scope='CLOUDFRONT', NextMarker=response['NextMarker'])
    web_acls += response['WebACLs']

    logger.debug(f"Discovered {len(web_acls)} WebACLs in {target_account.account_name}")

    for acl in web_acls:
        response = client.get_web_acl(Name=acl['Name'], Scope='CLOUDFRONT', Id=acl['Id'])
        process_v2_acl(client, response['WebACL'], target_account, "global")



def process_v2_acl(client, my_WebACL, target_account, region):
    resource_item = {}
    resource_item['awsAccountId']                   = target_account.account_id
    resource_item['awsAccountName']                 = target_account.account_name
    resource_item['resourceType']                   = "AWS::WAFv2::WebACL"
    resource_item['source']                         = "Antiope"

    resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
    resource_item['awsRegion']                      = region
    resource_item['configuration']                  = my_WebACL
    # TODO Tags?
    resource_item['supplementaryConfiguration']     = {}
    resource_item['resourceId']                     = my_WebACL['Id']
    resource_item['resourceName']                   = my_WebACL['Name']
    resource_item['ARN']                            = my_WebACL['ARN']
    resource_item['errors']                         = {}

    try:
        response = client.get_logging_configuration(ResourceArn=my_WebACL['ARN'])
        if 'LoggingConfiguration' in response:
            resource_item['supplementaryConfiguration']['LoggingConfiguration'] = response['LoggingConfiguration']
    except ClientError as e:
        if e.response['Error']['Code'] == "WAFNonexistentItemException":
            # Then the WAF has no logging config, so do nothing
            pass
        else:
            message = f"Error getting the LoggingConfiguration for WebACL {my_WebACL['Id']} in {region} for {target_account.account_name}: {e}"
            resource_item['errors']['LoggingConfiguration'] = message
            logger.warning(message)

    if region != "global":
        # This doesn't work for CloudFront Distributions
        try:
            response = client.list_resources_for_web_acl(WebACLArn=my_WebACL['ARN'])
            if 'ResourceArns' in response:
                resource_item['supplementaryConfiguration']['AssociatedResourceArns'] = response['ResourceArns']
        except ClientError as e:
            if e.response['Error']['Code'] == "WAFNonexistentItemException":
                # Then the WAF has no logging config, so do nothing
                pass
            else:
                message = f"Error getting the AssociatedResourceArns for WebACL {my_WebACL['Id']} in {region} for {target_account.account_name}: {e}"
                resource_item['errors']['AssociatedResourceArns'] = message
                logger.warning(message)

    save_resource_to_s3(WAFv2_PATH, resource_item['resourceId'], resource_item)


