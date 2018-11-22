
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

RESOURCE_PATH = "lambda"

def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        for r in target_account.get_regions():
            discover_lambdas(target_account, r)

    except AssumeRoleError as e:
        logger.error("Unable to assume role into account {}({})".format(target_account.account_name, target_account.account_id))
        return()
    except ClientError as e:
        logger.error("AWS Error getting info for {}: {}".format(target_account.account_name, e))
        return()
    except Exception as e:
        logger.error("{}\nMessage: {}\nContext: {}".format(e, message, vars(context)))
        raise

def discover_lambdas(target_account, region):
    '''Iterate across all regions to discover Lambdas'''

    lambdas = []
    client = target_account.get_client('lambdas', region=region)
    response = client.list_functions()
    while 'NextToken' in response:  # Gotta Catch 'em all!
        lambdas += response['Functions']
        response = client.list_functions(NextToken=response['NextToken'])
    lambdas += response['Functions']

    for l in lambdas:
        process_lambdas(client, l, target_account, region)

def process_lambdas(client, lambdas, target_account, region):

    resource_name = "{}-{}-{}".format(target_account.account_id, region, lambdas['Name'].replace("/", "-"))

    response = client.get_policy(FunctionName=lambdas['ARN'])
    if 'Policy' in response:
        lambdas['Policy']    = json.loads(response['Policy'])

    lambdas['resource_type']     = "lambdas"
    lambdas['region']            = region
    lambdas['account_id']        = target_account.account_id
    lambdas['account_name']      = target_account.account_name
    lambdas['last_seen']         = str(datetime.datetime.now(tz.gettz('US/Eastern')))
    save_resource_to_s3(RESOURCE_PATH, resource_name, lambdas)
