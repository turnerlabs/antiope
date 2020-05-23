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

RESOURCE_PATH = "support/trustedadvisorcheckresult"

# TA Checks by category (as of 3/6/19)
#  9             "category": "cost_optimizing",
# 24             "category": "fault_tolerance",
# 11             "category": "performance",
# 17             "category": "security",
# 48             "category": "service_limits",

# This is what I think we should care about
CATEGORIES = ['security', 'fault_tolerance', 'service_limits']


def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        support_client = target_account.get_client('support', region="us-east-1")  # Support API is in us-east-1 only
        checks = get_checks(target_account, support_client)
        for c in checks:
            process_ta_check(target_account, support_client, c)

    except AntiopeAssumeRoleError as e:
        logger.error("Unable to assume role into account {}({})".format(target_account.account_name, target_account.account_id))
        return()
    except ClientError as e:
        if e.response['Error']['Code'] == "SubscriptionRequiredException":
            logger.error("Premium support is not enabled in {}({})".format(target_account.account_name, target_account.account_id))
            capture_error(message, context, e, "Premium support is not enabled in {}({})".format(target_account.account_name, target_account.account_id))
            return()
        else:
            logger.critical("AWS Error getting info for {}: {}".format(target_account.account_name, e))
            capture_error(message, context, e, "ClientError for {}: {}".format(message['account_id'], e))
            raise
    except Exception as e:
        logger.critical("{}\nMessage: {}\nContext: {}".format(e, message, vars(context)))
        capture_error(message, context, e, "General Exception for {}: {}".format(message['account_id'], e))
        raise


def get_checks(target_account, client):
    '''Get a List of all the trusted advisor checks, return those that match CATEGORIES'''

    checks = []
    response = client.describe_trusted_advisor_checks(language='en')
    for c in response['checks']:
        if c['category'] in CATEGORIES:
            checks.append(c)
    return(checks)


def process_ta_check(target_account, client, c):
    '''Get the check results for each check'''

    response = client.describe_trusted_advisor_check_result(checkId=c['id'])
    if 'result' not in response:
        logger.error(f"Unable to get TA Check Results for checkId {c['id']} / {c['name']}")
        return()

    check = response['result']
    logger.debug(check)

    # There are a lot of TA checks. We don't need to capture the ones where it's all Ok.
    if check['status'] == "ok":
        return()

    # Don't save ENIs that already exist. They don't change much.
    if check_exists(RESOURCE_PATH, check['checkId']):
        return()


    resource_item = {}
    resource_item['awsAccountId']                   = target_account.account_id
    resource_item['awsAccountName']                 = target_account.account_name
    resource_item['resourceType']                   = "AWS::TrustedAdvisor::CheckResult"
    resource_item['source']                         = "Antiope"

    resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
    resource_item['configuration']                  = check
    resource_item['supplementaryConfiguration']     = {}
    resource_item['supplementaryConfiguration']['CheckData'] = c
    resource_item['resourceId']                     = check['checkId']
    resource_item['resourceName']                   = c['name']
    resource_item['errors']                         = {}

    save_resource_to_s3(RESOURCE_PATH, f"{target_account.account_id}-{check['checkId']}", resource_item)

def check_exists(path, check_id):
    s3client = boto3.client('s3')
    try:
        response = s3client.head_object(
            Bucket=os.environ['INVENTORY_BUCKET'],
            Key=f"Resources/{path}/{check_id}.json"
        )
        if response['LastModified'] > datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=15):
            return(True)
        else:
            return(False)
    except ClientError as e: # Object is missing, or othererror
        return(False)
