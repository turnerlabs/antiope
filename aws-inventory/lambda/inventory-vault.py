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
from botocore.exceptions import ClientError, EndpointConnectionError
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

RESOURCE_PATH = "backup/backupvault"


def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        # Now get the regional ones
        for r in target_account.get_regions():
            try:
                discover_vaults(target_account, r)
            except ClientError as e:
                # Move onto next region if we get access denied. This is probably SCPs
                if e.response['Error']['Code'] == 'AccessDeniedException':
                    logger.error(f"AccessDeniedException for region {r} in function {context.function_name} for {target_account.account_name}({target_account.account_id})")
                    continue
                else:
                    raise  # pass on to the next handlier
            except EndpointConnectionError as e:
                # Great, Another region that was introduced without GuardDuty Support
                logger.warning(f"EndpointConnectionError for vault in region {r}")

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


def discover_vaults(target_account, region):
    '''Find and process all the AWS Backup Valuts'''

    vaults = []
    client = target_account.get_client('backup', region=region)
    response = client.list_backup_vaults()
    while 'NextToken' in response:  # Gotta Catch 'em all!
        vaults += response['BackupVaultList']
        response = client.list_backup_vaults(NextToken=response['NextToken'])
    vaults += response['BackupVaultList']

    logger.debug(f"Discovered {len(vaults)} BackupVaults in {target_account.account_name}")

    for v in vaults:

        resource_item = {}
        resource_item['awsAccountId']                   = target_account.account_id
        resource_item['awsAccountName']                 = target_account.account_name
        resource_item['resourceType']                   = "AWS::Backup::BackupVault"
        resource_item['source']                         = "Antiope"

        resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
        resource_item['awsRegion']                      = region
        resource_item['configuration']                  = v
        # TODO Tags?
        resource_item['supplementaryConfiguration']     = {}
        resource_item['resourceId']                     = v['BackupVaultArn'].replace(':', '-')
        resource_item['resourceName']                   = v['BackupVaultName']
        resource_item['ARN']                            = v['BackupVaultArn']
        resource_item['errors']                         = {}

        save_resource_to_s3(RESOURCE_PATH, resource_item['resourceId'], resource_item)


