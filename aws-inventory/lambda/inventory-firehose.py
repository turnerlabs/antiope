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

FIREHOSE_PATH = "kinesisfirehose/deliverystream"


def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        for r in target_account.get_regions():
            try:
                discover_firehose(target_account, r)
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


def discover_firehose(target_account, region):
    '''Find and process all the REGIONAL AWS WAFv2'''

    firehoses = []
    client = target_account.get_client('firehose', region=region)
    response = client.list_delivery_streams()
    while 'HasMoreDeliveryStreams' in response and response['HasMoreDeliveryStreams'] is True:  # Gotta Catch 'em all!
        firehoses += response['DeliveryStreamNames']
        response = client.list_delivery_streams(ExclusiveStartDeliveryStreamName=response['DeliveryStreamNames'][-1])
    firehoses += response['DeliveryStreamNames']

    logger.debug(f"Discovered {len(firehoses)} Firehose Delivery Streams in {target_account.account_name}")

    for firehose_name in firehoses:
        delivery_stream = client.describe_delivery_stream(DeliveryStreamName=firehose_name)['DeliveryStreamDescription']

        resource_item = {}
        resource_item['awsAccountId']                   = target_account.account_id
        resource_item['awsAccountName']                 = target_account.account_name
        resource_item['resourceType']                   = "AWS::KinesisFirehose::DeliveryStream"
        resource_item['source']                         = "Antiope"

        resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
        resource_item['awsRegion']                      = region
        resource_item['configuration']                  = delivery_stream
        # TODO Tags?
        resource_item['supplementaryConfiguration']     = {}
        resource_item['resourceId']                     = f"{target_account.account_id}-{region}-{delivery_stream['DeliveryStreamName']}"
        resource_item['resourceName']                   = delivery_stream['DeliveryStreamName']
        resource_item['ARN']                            = delivery_stream['DeliveryStreamARN']
        resource_item['errors']                         = {}

        save_resource_to_s3(FIREHOSE_PATH, resource_item['resourceId'], resource_item)


