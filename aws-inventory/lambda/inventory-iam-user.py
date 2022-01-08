# Copyright 2019-2020 Turner Broadcasting Inc. / WarnerMedia
# Copyright 2021 Chris Farris <chrisf@primeharbor.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import boto3
from botocore.exceptions import ClientError
import json
import os
import time
from datetime import datetime, timezone
from dateutil import tz
import re
from xml.dom.minidom import parseString

from antiope.aws_account import *
from common import *

import logging
logger = logging.getLogger()
logger.setLevel(getattr(logging, os.getenv('LOG_LEVEL', default='INFO')))
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

USER_RESOURCE_PATH = "iam/user"

def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        discover_users(target_account)

    except AntiopeAssumeRoleError as e:
        logger.error("Unable to assume role into account {}({})".format(target_account.account_name, target_account.account_id))
        return()
    except ClientError as e:
        logger.critical("AWS Error getting info for {}: {}".format(message['account_id'], e))
        capture_error(message, context, e, "ClientError for {}: {}".format(message['account_id'], e))
        raise
    except Exception as e:
        logger.critical("{}\nMessage: {}\nContext: {}".format(e, message, vars(context)))
        capture_error(message, context, e, "General Exception for {}: {}".format(message['account_id'], e))
        raise


def discover_users(account):
    '''
        Queries AWS to determine IAM Users exist in an AWS Account
    '''
    users = []

    iam_client = account.get_client('iam')
    response = iam_client.list_users()
    while 'IsTruncated' in response and response['IsTruncated'] is True:  # Gotta Catch 'em all!
        users += response['Users']
        response = iam_client.list_users(Marker=response['Marker'])
    users += response['Users']

    resource_item = {}
    resource_item['awsAccountId']                   = account.account_id
    resource_item['awsAccountName']                 = account.account_name
    resource_item['resourceType']                   = "AWS::IAM::User"
    resource_item['source']                         = "Antiope"

    for user in users:
        resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
        resource_item['configuration']                  = user
        resource_item['supplementaryConfiguration']     = {}
        resource_item['resourceId']                     = user['UserId']
        resource_item['resourceName']                   = user['UserName']
        resource_item['ARN']                            = user['Arn']
        resource_item['resourceCreationTime']           = user['CreateDate']
        resource_item['errors']                         = {}

        response = iam_client.list_mfa_devices(UserName=user['UserName'])
        if 'MFADevices' in response and len(response['MFADevices']) > 0:
            resource_item['supplementaryConfiguration']['MFADevice'] = response['MFADevices'][0]

        response = iam_client.list_access_keys(UserName=user['UserName'])
        if 'AccessKeyMetadata' in response and len(response['AccessKeyMetadata']) > 0:
            resource_item['supplementaryConfiguration']['AccessKeyMetadata'] = response['AccessKeyMetadata']

        try:
            response = iam_client.get_login_profile(UserName=user['UserName'])
            if 'LoginProfile' in response:
                resource_item['supplementaryConfiguration']['LoginProfile'] = response["LoginProfile"]
        except ClientError as e:
            if e.response['Error']['Code'] == "NoSuchEntity":
                pass
            else:
                raise

        try:
            response = iam_client.list_user_tags(UserName=user['UserName'])
            if 'Tags' in response:
                resource_item['tags'] = parse_tags(response['Tags'])
        except ClientError as e:
            if e.response['Error']['Code'] == "NoSuchEntity":
                pass
            else:
                raise

        save_resource_to_s3(USER_RESOURCE_PATH, resource_item['resourceId'], resource_item)

