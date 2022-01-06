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

from antiope.aws_account import *
from common import *

import logging
logger = logging.getLogger()
logger.setLevel(getattr(logging, os.getenv('LOG_LEVEL', default='INFO')))
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

RESOURCE_PATH = "storage_gateway/gateway"
TYPE = "AWS::ElasticLoadBalancingV2::LoadBalancer"


def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        for r in target_account.get_regions():
            try:
                discover_storage_gateways(target_account, r)
            except ClientError as e:
                if e.response['Error']['Code'] == 'AccessDenied':
                    logger.warning(f"AccessDenied attempting to discover ELBs in {target_account.account_name} ({target_account.account_id}) in region {r}: {e}")
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


def discover_storage_gateways(target_account, region):
    '''Discover all Storage Gateways'''


    sgw_client = target_account.get_client('storagegateway', region=region)
    response = sgw_client.list_gateways()
    while 'Marker' in response:  # Gotta Catch 'em all!
        for sgws in response.get("Gateways"):
            sgw = sgw_client.describe_gateway_information(GatewayARN=sgws.get("GatewayARN"))
            resource_item = {
                "awsAccountId":                 target_account.account_id,
                "awsAccountName":               target_account.account_name,
                "resourceType":                 TYPE,
                "configurationItemCaptureTime": str(datetime.datetime.now()),
                "awsRegion":                    region,
                "configuration":                sgw,
                "supplementaryConfiguration":   {},
                "resourceName":                 sgw.get("GatewayName"),
                "resourceId":                   f"{target_account.acount_id}-{region}-{sgw.get('GatewayName')}",
                "ARN":                          sgw.get("GatewayARN"),
                "resourceCreationTime":         sgw.get("DateCreated", None),
                "errors":                       {}
            }
        response = sgw_client.list_gateways(Marker=response.get("Marker"))

        save_resource_to_s3(RESOURCE_PATH, resource_item['resourceId'], resource_item)

