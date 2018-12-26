
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
    client = target_account.get_client('lambda', region=region)
    response = client.list_functions()
    while 'NextMarker' in response:  # Gotta Catch 'em all!
        lambdas += response['Functions']
        response = client.list_functions(Marker=response['NextMarker'])
    lambdas += response['Functions']

    for l in lambdas:
        process_lambda(client, l, target_account, region)

def process_lambda(client, mylambda, target_account, region):

    resource_item = {}
    resource_item['awsAccountId']                   = target_account.account_id
    resource_item['awsAccountName']                 = target_account.account_name
    resource_item['resourceType']                   = "AWS::Lambda::Function"
    resource_item['source']                         = "Antiope"

    resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
    resource_item['awsRegion']                      = region
    resource_item['configuration']                  = mylambda
    # resource_item['tags']                           = FIXME
    resource_item['supplementaryConfiguration']     = {}
    resource_item['resourceId']                     = "{}-{}-{}".format(target_account.account_id, region, mylambda['FunctionName'].replace("/", "-"))
    resource_item['resourceName']                   = mylambda['FunctionName']
    resource_item['ARN']                            = mylambda['FunctionArn']
    resource_item['errors']                         = {}

    response = client.get_policy(FunctionName=mylambda['FunctionArn'])
    if 'Policy' in response:
        resource_item['supplementaryConfiguration']['Policy']    = json.loads(response['Policy'])



    save_resource_to_s3(RESOURCE_PATH, resource_item['resourceId'], resource_item)
