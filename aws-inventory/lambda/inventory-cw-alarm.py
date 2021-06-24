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

METRIC_PATH = "cloudwatch/alarm"
COMPOSITE_PATH = "cloudwatch/composite_alarm"


def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        for r in target_account.get_regions(service='cloudwatch'):
            try:
                discover_alarms(target_account, r)
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


def discover_alarms(target_account, region):
    '''Find and process all the CloudWatch Alarms in ALARM State'''

    metric_alarms = []
    composite_alarms = []
    client = target_account.get_client('cloudwatch', region=region)
    response = client.describe_alarms(StateValue='ALARM')
    while 'NextToken' in response:  # Gotta Catch 'em all!
        metric_alarms += response['MetricAlarms']
        composite_alarms += response['CompositeAlarms']
        response = client.describe_alarms(StateValue='ALARM', NextToken=response['NextToken'])
    metric_alarms += response['MetricAlarms']
    composite_alarms += response['CompositeAlarms']

    logger.debug(f"Discovered {len(metric_alarms)} Alarms in {target_account.account_name}")
    logger.debug(f"Discovered {len(composite_alarms)} CompositeAlarms in {target_account.account_name}")

    for a in metric_alarms:
        resource_item = {}
        resource_item['awsAccountId']                   = target_account.account_id
        resource_item['awsAccountName']                 = target_account.account_name
        resource_item['resourceType']                   = "AWS::CloudWatch::Alarm"
        resource_item['source']                         = "Antiope"
        resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
        resource_item['awsRegion']                      = region
        resource_item['configuration']                  = a
        resource_item['supplementaryConfiguration']     = {}
        resource_item['resourceId']                     = f"{a['AlarmName']}-{target_account.account_id}-{region}"
        resource_item['resourceName']                   = a['AlarmName']
        resource_item['ARN']                            = a['AlarmArn']
        resource_item['errors']                         = {}
        save_resource_to_s3(METRIC_PATH, resource_item['resourceId'], resource_item)

    for a in composite_alarms:
        resource_item = {}
        resource_item['awsAccountId']                   = target_account.account_id
        resource_item['awsAccountName']                 = target_account.account_name
        resource_item['resourceType']                   = "AWS::CloudWatch::CompositeAlarm"
        resource_item['source']                         = "Antiope"
        resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
        resource_item['awsRegion']                      = region
        resource_item['configuration']                  = a
        resource_item['supplementaryConfiguration']     = {}
        resource_item['resourceId']                     = f"{a['AlarmName']}-{target_account.account_id}-{region}"
        resource_item['resourceName']                   = a['AlarmName']
        resource_item['ARN']                            = a['AlarmArn']
        resource_item['errors']                         = {}
        save_resource_to_s3(COMPOSITE_PATH, resource_item['resourceId'], resource_item)

