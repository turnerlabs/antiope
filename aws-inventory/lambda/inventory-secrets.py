
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


RESOURCE_PATH = "secretsmanager/secret"


def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        for r in target_account.get_regions():
            try:
                discover_secrets(target_account, r)
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


def discover_secrets(target_account, region):
    '''Iterate across all regions to discover Cloudsecrets'''

    try:
        secrets = []
        client = target_account.get_client('secretsmanager', region=region)
        response = client.list_secrets()
        while 'NextToken' in response:  # Gotta Catch 'em all!
            secrets += response['SecretList']
            response = client.list_secrets(NextToken=response['NextToken'])
        secrets += response['SecretList']

        for s in secrets:
            process_secret(client, s, target_account, region)

    except EndpointConnectionError as e:
        logger.info("Region {} not supported".format(region))


def process_secret(client, secret, target_account, region):
    resource_item = {}
    resource_item['awsAccountId']                   = target_account.account_id
    resource_item['awsAccountName']                 = target_account.account_name
    resource_item['resourceType']                   = "AWS::SecretsManager::Secret"
    resource_item['source']                         = "Antiope"
    resource_item['awsRegion']                      = region
    resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
    resource_item['configuration']                  = secret
    resource_item['supplementaryConfiguration']     = {}
    resource_item['resourceId']                     = "{}-{}-{}".format(target_account.account_id, region, secret['Name'].replace("/", "-"))
    resource_item['resourceName']                   = secret['Name']
    resource_item['errors']                         = {}
    resource_item['ARN']                            = secret['ARN']

    try:
        response = client.get_resource_policy(SecretId=secret['ARN'])
        if 'ResourcePolicy' in response:
            resource_item['supplementaryConfiguration']['ResourcePolicy']    = json.loads(response['ResourcePolicy'])
    except ClientError as e:
        if e.response['Error']['Code'] == "AccessDeniedException":
            resource_item['errors']['ResourcePolicy'] = e.response['Error']['Message']
        else:
            raise

    if 'Tags' in secret:
        resource_item['tags']              = parse_tags(secret['Tags'])

    save_resource_to_s3(RESOURCE_PATH, resource_item['resourceId'], resource_item)
