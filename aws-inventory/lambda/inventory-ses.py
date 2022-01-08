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
from botocore.exceptions import ClientError, ConnectTimeoutError
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

RESOURCE_PATH = "ses/identity"
RESOURCE_TYPE = "AWS::SES::Identity"

def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        for region in target_account.get_regions():
            try:
                client = target_account.get_client('sesv2', region=region)
                identities = discover_identities(client)
                for i in identities:
                    try:
                        process_identity(target_account, region, i, client)
                    except ClientError as e:
                        if e.response['Error']['Code'] == 'TooManyRequestsException':
                            sleep(1)
                            process_identity(target_account, region, i, client)
                        else:
                            raise
            except ClientError as e:
                if e.response['Error']['Code'] == 'AccessDeniedException':
                    logger.warning(f"Access Denied for SES in region {region} for account {target_account.account_name}({target_account.account_id}): {e}")
                    continue
                else:
                    raise
            except ConnectTimeoutError as e:
                logger.warning(f"Access Denied for SES in region {region} for account {target_account.account_name}({target_account.account_id}): {e}")
                continue


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


def discover_identities(client):
    '''Discover all SES Identities'''

    identities = []
    response = client.list_email_identities()
    while 'NextToken' in response:  # Gotta Catch 'em all!
        identities += response['EmailIdentities']
        response = client.list_email_identities(NextToken=response['NextToken'])
    identities += response['EmailIdentities']
    return(identities)

def process_identity(account, region, i, client):

    identity = client.get_email_identity(EmailIdentity=i['IdentityName'])
    del(identity['ResponseMetadata'])
    resource_item = {}
    resource_item['awsAccountId']                   = account.account_id
    resource_item['awsAccountName']                 = account.account_name
    resource_item['resourceType']                   = RESOURCE_TYPE
    resource_item['source']                         = "Antiope"
    resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
    resource_item['awsRegion']                      = region
    resource_item['configuration']                  = identity
    resource_item['supplementaryConfiguration']     = {}
    resource_item['resourceName']                   = i['IdentityName']
    resource_item['resourceId']                     = f"{account.account_id}-{region}-{i['IdentityName']}"
    resource_item['errors']                         = {}
    resource_item['tags']                           = parse_tags(identity['Tags'])

    save_resource_to_s3(RESOURCE_PATH, resource_item['resourceId'], resource_item)

