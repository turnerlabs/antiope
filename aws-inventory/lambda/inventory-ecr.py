
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

RESOURCE_PATH = "ecr/repositories"

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
        response = client.list_secrets(nextToken=response['nextToken'])
    repos += response['repositories']

    for r in repos:
        process_repo(client, r, target_account, region)

def process_repo(client, repo, target_account, region):

    resource_name = "{}-{}-{}".format(target_account.account_id, region, repo['repositoryName'].replace("/", "-"))

    try:
        response = client.get_repository_policy(repositoryName=repo['repositoryName'])
        if 'policyText' in response:
            repo['ResourcePolicy']    = json.loads(response['policyText'])
    except ClientError as e:
        if e.response['Error']['Code'] == 'RepositoryPolicyNotFoundException':
            pass
        else:
            raise

    # if 'Tags' in repo:
    #     repo['Tags']              = parse_tags(repo['Tags'])

    repo['resource_type']     = "ecr-repositories"
    repo['region']            = region
    repo['account_id']        = target_account.account_id
    repo['account_name']      = target_account.account_name
    repo['last_seen']         = str(datetime.datetime.now(tz.gettz('US/Eastern')))
    save_resource_to_s3(RESOURCE_PATH, resource_name, repo)


