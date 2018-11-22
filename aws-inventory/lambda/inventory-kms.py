
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
    key['Aliases'] = get_key_aliases(client, key_arn)
    key['ResourcePolicy'] = get_key_policy(client, key_arn)
    key['Tags'] = get_key_tags(client, key_arn)
    key['Grants'] = get_key_grants(client, key_arn)

    # Remove redundant key
    key.pop('AWSAccountId')

    key['resource_type']     = "kms-key"
    key['region']            = region
    key['account_id']        = target_account.account_id
    key['account_name']      = target_account.account_name
    key['last_seen']         = str(datetime.datetime.now(tz.gettz('US/Eastern')))
    save_resource_to_s3(RESOURCE_PATH, resource_name, repo)

def get_key_grants(client, key_arn):
    '''Returns a list of Grants for Key

    Args:
        client: Boto3 Client, connected to account and region
        key_arn (string): ARN of key

    Returns:
        list(dict): List of Grants for Key

    '''

    grants = []
    response = client.list_grants(KeyId=key_arn)
    while response['Truncated']:
        grants += response['Grants']
        response = client.list_grants(KeyId=key_arn, Marker=response['NextMarker'])
    grants += response['Grants']
    return grants
    
def get_key_aliases(client, key_arn):
    '''Return List of Aliases for Key
    
    Args:
        client: Boto3 Client, connected to account and region
        key_arn (string): ARN of Key

    Returns:
        list(str): List of Alias Names for Key

    '''

    aliases = []
    response = client.list_aliases(KeyId=key_arn)
    while response['Truncated']:
        aliases += response['Aliases']
        response = client.list_aliases(KeyId=key_arn, Marker=response['NextMarker'])
    aliases += response['Aliases']
    return map(lambda x: x['AliasName'], aliases)

def get_key_policy(client, key_arn):
    '''Return ResourcePolicy of Key

    Args:
        client: Boto3 Client, connected to account and region
        key_arn (string): ARN of Key
    
    Returns: 
        dict: Resource Policy of Key
    
    '''

    policies = get_policy_list(client, key_arn)
    
    if len(policies) == 1 and policies[0] == 'default':
        return json.loads(client.get_key_policy(KeyId=key_arn, PolicyName=policies[0])['Policy'])
    else:
        policy = {}
        for p in policies:
            policy[p] = json.loads(client.get_key_policy(KeyId=key_arn, PolicyName=p)['Policy'])
        return policy

def get_policy_list(client, key_arn):
    '''Return list of policies affecting key. Right now, should only be default.

    Args:
        client: Boto3 Client, connected to account and region
        key_arn (string): ARN of Key

    Returns:
        dict: Resource Policy of Key
    
    '''

    policies = []
    response = client.list_key_policies(KeyId=key_arn)
    while response['Truncated']:
        policies += response['PolicyNames']
        response = client.list_key_policies(KeyId=key_arn, Marker=response['NextMarker'])
    policies += response['PolicyNames']
    return policies

def get_key_tags(client, key_arn):
    '''Return list of tags for key

    Args:
        client: Boto3 Client, connected to account and region
        key_arn (string): ARN of Key

    Returns:
        list(str): List of tags for key

    '''

    unparsed_tags = []
    response = client.list_resource_tags(KeyId=key_arn)
    while response['Truncated']:
        unparsed_tags += response('Tags')
        response = client.list_resource_tags(KeyId=key_arn, Marker=resource['NextMarker'])
    unparsed_tags += response('Tags')
    
    tags = []
    for tag in unparsed_tags:
        tags += kms_parse_tags(tag)
    return tags

def kms_parse_tags(tagset):
    '''Format list of tag to something easily consumable in Splunk

    This function would not be necessary if AWS SDK were consistent

    Args:
        tagset (dict): Single tag in following format: {'TagKey': 'Foo', 'TagValue': 'Bar'}

    Returns:
        dict: Tag in following format: {'Tag': 'Value'}

    '''

    output = {}
    for tag in tagset:
        output[tag['TagKey']] = tag['TagValue']
    return(output)
