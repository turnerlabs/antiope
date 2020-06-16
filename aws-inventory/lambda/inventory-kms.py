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

RESOURCE_PATH = "kms/key"


def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        for r in target_account.get_regions():
            try:
                discover_keys(target_account, r)
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
    # Enhance Key Information to include CMK Policy, Aliases, Tags
    try:
        key = client.describe_key(KeyId=key_arn)['KeyMetadata']
    except ClientError as e:
        if e.response['Error']['Code'] == 'AccessDeniedException':
            logger.error(f"Unable to get details of key {key_arn}: AccessDenied")
            return()
        else:
            raise

    resource_item = {}
    resource_item['awsAccountId']                   = target_account.account_id
    resource_item['awsAccountName']                 = target_account.account_name
    resource_item['resourceType']                   = "AWS::KMS::Key"
    resource_item['source']                         = "Antiope"

    resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
    resource_item['awsRegion']                      = region
    resource_item['configuration']                  = key
    resource_item['supplementaryConfiguration']     = {}
    resource_item['resourceId']                     = key['KeyId']
    resource_item['ARN']                            = key['Arn']
    resource_item['errors']                         = {}

    try:
        resource_item['tags']                           = client.list_resource_tags(KeyId=key['KeyId'])
    except ClientError as e:
        if e.response['Error']['Code'] == 'NotFoundException':
            pass
        elif e.response['Error']['Code'] == 'AccessDeniedException':
            resource_item['errors']['ResourceTags-Error'] = e.response['Error']['Message']
        else:
            raise

    try:
        aliases = get_key_aliases(client, key_arn)
        if aliases:
            resource_item['supplementaryConfiguration']['Aliases'] = aliases
    except ClientError as e:
        if e.response['Error']['Code'] == 'NotFoundException':
            pass
        elif e.response['Error']['Code'] == 'AccessDeniedException':
            resource_item['errors']['Aliases-Error'] = e.response['Error']['Message']
        else:
            raise

    try:
        policies = get_policy_list(client, key_arn)
        policy = get_key_policy(client, key_arn, policies)
        if policy:
            resource_item['supplementaryConfiguration']['ResourcePolicy'] = policy
    except ClientError as e:
        if e.response['Error']['Code'] == 'NotFoundException':
            pass
        elif e.response['Error']['Code'] == 'AccessDeniedException':
            resource_item['errors']['ResourcePolicy-Error'] = e.response['Error']['Message']
        else:
            raise

    try:
        tags = get_key_tags(client, key_arn)
        if tags:
            resource_item['tags'] = tags
    except ClientError as e:
        if e.response['Error']['Code'] == 'NotFoundException':
            pass
        elif e.response['Error']['Code'] == 'AccessDeniedException':
            resource_item['errors']['Tags-Error'] = e.response['Error']['Message']
        else:
            raise

    try:
        grants = get_key_grants(client, key_arn)
        if grants:
            resource_item['supplementaryConfiguration']['Grants'] = grants
    except ClientError as e:
        if e.response['Error']['Code'] == 'NotFoundException':
            pass
        elif e.response['Error']['Code'] == 'AccessDeniedException':
            resource_item['errors']['Grants-Error'] = e.response['Error']['Message']
        else:
            raise

    save_resource_to_s3(RESOURCE_PATH, resource_item['resourceId'], resource_item)


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


def get_key_policy(client, key_arn, policies):
    '''Return ResourcePolicy of Key

    For right now, the only valid policy name is 'default', as per
    https://docs.aws.amazon.com/kms/latest/APIReference/API_GetKeyPolicy.html

    However, the existence of the ListKeyPolicies method implies that
    this might not be the case in the future.

    Args:
        client: Boto3 Client, connected to account and region
        key_arn (string): ARN of Key

    Returns:
        dict: Resource Policy of Key

    '''

    if len(policies) == 1 and policies[0] == 'default':
        response = client.get_key_policy(KeyId=key_arn, PolicyName=policies[0])
        if 'Policy' in response:
            return json.loads(response['Policy'])
    else:
        for p in policies:
            response = client.get_key_policy(KeyId=key_arn, PolicyName=p)
            if 'Policy' in response:
                policy[p] = json.loads(response['Policy'])
            return policy
    # Just in case of NotFoundException
    return None


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
        unparsed_tags += response['Tags']
        response = client.list_resource_tags(KeyId=key_arn, Marker=resource['NextMarker'])
    unparsed_tags += response['Tags']

    return(kms_parse_tags(unparsed_tags))


def kms_parse_tags(tagset):
    '''Format list of tag to something easily consumable in Splunk

    This function would not be necessary if AWS SDK were consistent

    Args:
        tagset (dict): Single tag in following format: {'TagKey': 'Foo', 'TagValue': 'Bar'}

    Returns:
        dict: Tag in following format: {'Tag': 'Value'}

    '''

    try:
        output = {}
        for tag in tagset:
            output[tag['TagKey']] = tag['TagValue']
        return(output)
    except Exception as e:
        logger.error("Unable to parse tagset {}: {}".format(tagset, e))
        raise
