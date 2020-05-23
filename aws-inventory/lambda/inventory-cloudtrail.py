
import boto3
from botocore.exceptions import ClientError

import json
import os
import time
import datetime
from dateutil import tz

from antiope.aws_account import *
from common import *

import logging
logger = logging.getLogger()
logger.setLevel(getattr(logging, os.getenv('LOG_LEVEL', default='INFO')))
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

RESOURCE_PATH = "cloudtrail/trail"
RESOURCE_TYPE = "AWS::CloudTrail::Trail"


def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        for r in target_account.get_regions():
            discover_trails(target_account, r)

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


def discover_trails(target_account, region):
    '''Iterate across all regions to discover CloudTrails'''

    ct_client = target_account.get_client('cloudtrail', region=region)
    response = ct_client.describe_trails()

    resource_item = {}
    resource_item['awsAccountId']                   = target_account.account_id
    resource_item['awsAccountName']                 = target_account.account_name
    resource_item['resourceType']                   = RESOURCE_TYPE
    resource_item['awsRegion']                      = region
    resource_item['source']                         = "Antiope"

    for trail in response['trailList']:

        # CloudTrail will return trails from other regions if that trail is collecting events from the region where the api call was made
        if region != trail['TrailARN'].split(":")[3]:
            # Move along if the region of the trail is not the region we're making the call to
            continue

        resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
        resource_item['configuration']                  = trail
        # resource_item['tags']                           = ct_client.list_tags(ResourceIdList=[ trail['TrailARN'] ] )
        resource_item['supplementaryConfiguration']     = {}
        resource_item['resourceId']                     = "{}-{}-{}".format(trail['Name'], target_account.account_id, region)
        resource_item['resourceName']                   = trail['Name']
        resource_item['ARN']                            = trail['TrailARN']
        resource_item['errors']                         = {}

        event_response = ct_client.get_event_selectors(TrailName=trail['Name'])
        resource_item['supplementaryConfiguration']['EventSelectors'] = event_response['EventSelectors']

        status_response = ct_client.get_trail_status(Name=trail['Name'])
        resource_item['supplementaryConfiguration']['Status'] = status_response
        del(resource_item['supplementaryConfiguration']['Status']['ResponseMetadata'])

        save_resource_to_s3(RESOURCE_PATH, resource_item['resourceId'], resource_item)
