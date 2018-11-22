
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

KEY_RESOURCE_PATH = "kms/key"

def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        for r in target_account.get_regions():
            discover_keys(target_account, r)

    except AssumeRoleError as e:
        logger.error("Unable to assume role into account {}({})".format(target_account.account_name, target_account.account_id))
        return()
    except ClientError as e:
        logger.error("AWS Error getting info for {}: {}".format(target_account.account_name, e))
        return()
    except Exception as e:
        logger.error("{}\nMessage: {}\nContext: {}".format(e, message, vars(context)))
        raise

def discover_keys(target_account, region):
    '''Iterate across all regions to discover keys'''

    keys = []
    client = target_account.get_client('kms', region=region)
    response = client.list_keys()
    while response['Truncated']:
        keys += response['Keys']
        response = client.list_keys(Marker=response['NextMarker'])
    keys += response['Keys']

    for k in keys:
        process_key(client, k['KeyArn'], target_account, region)

def process_key(client, key_arn, target_account, region):
    '''Pull additional information for the key, and save to bucket'''
    resource_name = "{}-{}-{}".format(target_account.account_id, region, key['KeyId'].replace('/', '-'))

    # Enhance Key Information to include CMK Policy, Aliases, Tags
    key = client.describe_key(KeyId=key_arn)['KeyMetadata']

    # Remove redundant key
    key.pop('AWSAccountId')

    key['resource_type']     = "kms-key"
    key['region']            = region
    key['account_id']        = target_account.account_id
    key['account_name']      = target_account.account_name
    key['last_seen']         = str(datetime.datetime.now(tz.gettz('US/Eastern')))
    save_resource_to_s3(RESOURCE_PATH, resource_name, repo)
