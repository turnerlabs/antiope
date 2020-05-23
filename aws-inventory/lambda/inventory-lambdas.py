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

FUNC_PATH = "lambda/function"
LAYER_PATH = "lambda/layer"


def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        for r in target_account.get_regions():
            try:
                discover_lambdas(target_account, r)
                discover_lambda_layer(target_account, r)
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


def discover_lambdas(target_account, region):
    '''Iterate across all regions to discover Lambdas'''

    lambdas = []
    client = target_account.get_client('lambda', region=region)
    response = client.list_functions()
    while 'NextMarker' in response:  # Gotta Catch 'em all!
        lambdas += response['Functions']
        response = client.list_functions(Marker=response['NextMarker'])
    lambdas += response['Functions']

    logger.debug(f"Discovered {len(lambdas)} Lambda in {target_account.account_name}")

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
    if 'tags' in mylambda:
        resource_item['tags']                       = parse_tags(mylambda['tags'])
    resource_item['supplementaryConfiguration']     = {}
    resource_item['resourceId']                     = "{}-{}-{}".format(target_account.account_id, region, mylambda['FunctionName'].replace("/", "-"))
    resource_item['resourceName']                   = mylambda['FunctionName']
    resource_item['ARN']                            = mylambda['FunctionArn']
    resource_item['errors']                         = {}

    try:
        response = client.get_policy(FunctionName=mylambda['FunctionArn'])
        if 'Policy' in response:
            resource_item['supplementaryConfiguration']['Policy']    = json.loads(response['Policy'])
    except ClientError as e:
        message = f"Error getting the Policy for function {mylambda['FunctionName']} in {region} for {target_account.account_name}: {e}"
        resource_item['errors']['Policy'] = message
        logger.warning(message)

    save_resource_to_s3(FUNC_PATH, resource_item['resourceId'], resource_item)


def discover_lambda_layer(target_account, region):
    '''Iterate across all regions to discover Lambdas'''
    try:
        layers = []
        client = target_account.get_client('lambda', region=region)
        response = client.list_layers()
        while 'NextMarker' in response:  # Gotta Catch 'em all!
            layers += response['Layers']
            response = client.list_layers(Marker=response['NextMarker'])
        layers += response['Layers']

        for l in layers:
            process_layer(client, l, target_account, region)
    except AttributeError as e:
        import botocore
        logger.error(f"Unable to inventory Lambda Layers - Lambda Boto3 doesn't support yet. Boto3: {boto3.__version__} botocore: {botocore.__version__}")
        return()


def process_layer(client, layer, target_account, region):
    resource_item = {}
    resource_item['awsAccountId']                   = target_account.account_id
    resource_item['awsAccountName']                 = target_account.account_name
    resource_item['resourceType']                   = "AWS::Lambda::Layer"
    resource_item['source']                         = "Antiope"

    resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
    resource_item['awsRegion']                      = region
    resource_item['configuration']                  = layer
    if 'tags' in layer:
        resource_item['tags']                       = parse_tags(layer['tags'])
    resource_item['supplementaryConfiguration']     = {}
    resource_item['resourceId']                     = "{}-{}-{}".format(target_account.account_id, region, layer['LayerName'].replace("/", "-"))
    resource_item['resourceName']                   = layer['LayerName']
    resource_item['ARN']                            = layer['LayerArn']
    resource_item['errors']                         = {}

    try:
        resource_item['supplementaryConfiguration']['LayerVersions'] = []
        response = client.list_layer_versions(LayerName=layer['LayerName'], MaxItems=50)
        for version in response['LayerVersions']:
            version['Policy'] = client.get_layer_version_policy(LayerName=layer['LayerName'], VersionNumber=version['Version'])
            resource_item['supplementaryConfiguration']['LayerVersions'].append(version)
    except ClientError as e:
        message = f"Error getting the Policy for layer {layer['LayerName']} in {region} for {target_account.account_name}: {e}"
        resource_item['errors']['LayerVersions'] = message
        logger.warning(message)

    save_resource_to_s3(LAYER_PATH, resource_item['resourceId'], resource_item)
