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

RESOURCE_PATH = "guardduty/detector"
RESOURCE_TYPE = "AWS::GuardDuty::Detector"


def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        for r in target_account.get_regions():
            discover_detectors(target_account, r)

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


def discover_detectors(target_account, region):
    '''Iterate across all regions to discover Cloudsecrets'''

    detector_ids = []
    client = target_account.get_client('guardduty', region=region)
    response = client.list_detectors()
    while 'nextToken' in response:  # Gotta Catch 'em all!
        detector_ids += response['DetectorIds']
        response = client.list_detectors(nextToken=response['NextToken'])
    detector_ids += response['DetectorIds']

    for d in detector_ids:
        process_detector(client, d, target_account, region)


def process_detector(client, detector_id, target_account, region):

    response = client.get_detector(DetectorId=detector_id)

    del response['ResponseMetadata']  # We don't need this

    resource_item = {}
    resource_item['awsAccountId']                   = target_account.account_id
    resource_item['awsAccountName']                 = target_account.account_name
    resource_item['resourceType']                   = RESOURCE_TYPE
    resource_item['awsRegion']                      = region
    resource_item['source']                         = "Antiope"
    resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
    resource_item['configuration']                  = response
    resource_item['supplementaryConfiguration']     = {}
    resource_item['resourceId']                     = detector_id
    resource_item['resourceName']                   = f"Detector-{target_account.account_id}-{region}"
    resource_item['resourceCreationTime']           = response['CreatedAt']
    resource_item['errors']                         = {}

    response = client.get_master_account(DetectorId=detector_id)
    if 'Master' in response:
        resource_item['supplementaryConfiguration']['Master'] = response['Master']

    save_resource_to_s3(RESOURCE_PATH, resource_item['resourceId'], resource_item)
