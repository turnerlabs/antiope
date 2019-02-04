
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

RESOURCE_PATH = "ecr/repository"
RESOURCE_TYPE = "AWS::ECR::Repository"

def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        for r in target_account.get_regions():
            discover_repos(target_account, r)

    except AssumeRoleError as e:
        logger.error("Unable to assume role into account {}({})".format(target_account.account_name, target_account.account_id))
        return()
    except ClientError as e:
        logger.error("AWS Error getting info for {}: {}".format(target_account.account_name, e))
        return()
    except Exception as e:
        logger.error("{}\nMessage: {}\nContext: {}".format(e, message, vars(context)))
        raise

def discover_repos(target_account, region):
    '''Iterate across all regions to discover Cloudsecrets'''

    repos = []
    client = target_account.get_client('ecr', region=region)
    response = client.describe_repositories(registryId=target_account.account_id)
    while 'nextToken' in response:  # Gotta Catch 'em all!
        repos += response['repositories']
        response = client.describe_repositories(nextToken=response['nextToken'])
    repos += response['repositories']

    for r in repos:
        process_repo(client, r, target_account, region)

def process_repo(client, repo, target_account, region):

    resource_item = {}
    resource_item['awsAccountId']                   = target_account.account_id
    resource_item['awsAccountName']                 = target_account.account_name
    resource_item['resourceType']                   = RESOURCE_TYPE
    resource_item['awsRegion']                      = region
    resource_item['source']                         = "Antiope"
    resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
    resource_item['configuration']                  = repo
    resource_item['supplementaryConfiguration']     = {}
    resource_item['resourceId']                     = "{}-{}-{}".format(target_account.account_id, region, repo['repositoryName'].replace("/", "-"))
    resource_item['resourceName']                   = repo['repositoryName']
    resource_item['ARN']                            = repo['repositoryArn']
    resource_item['resourceCreationTime']           = repo['createdAt']
    resource_item['errors']                         = {}

    try:
        response = client.get_repository_policy(repositoryName=repo['repositoryName'])
        if 'policyText' in response:
            resource_item['supplementaryConfiguration']['ResourcePolicy']    = json.loads(response['policyText'])
    except ClientError as e:
        if e.response['Error']['Code'] == 'RepositoryPolicyNotFoundException':
            pass
        else:
            raise

    save_resource_to_s3(RESOURCE_PATH, resource_item['resourceId'], resource_item)


