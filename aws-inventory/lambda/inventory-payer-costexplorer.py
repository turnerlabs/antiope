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
from datetime import datetime, timezone, date
from dateutil import tz

from antiope.aws_account import *
from antiope.config import *
from antiope.aws_organization import *
from common import *

import logging
logger = logging.getLogger()
logger.setLevel(getattr(logging, os.getenv('LOG_LEVEL', default='DEBUG')))
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        antiope_config = AntiopeConfig()
        payer_account = AWSAccount(message['payer_id'], config=antiope_config)
        ce_client = payer_account.get_client('ce')

        today = date.today()
        start_of_this_month = today.replace(day=1)
        end_of_last_month = start_of_this_month - datetime.timedelta(days=1)
        start_of_last_month = end_of_last_month.replace(day=1)

        logger.debug(f"Today {today} - Start of Month: {start_of_this_month} - End of Last Month: {end_of_last_month} - Start of Last Month: {start_of_last_month}")

        # Get Last Month cost
        response = ce_client.get_cost_and_usage(
            TimePeriod={'Start': str(start_of_last_month), 'End': str(end_of_last_month) },
            Metrics=['UnblendedCost'],
            Granularity='MONTHLY',
            GroupBy=[{'Type': 'DIMENSION', 'Key': 'LINKED_ACCOUNT'}],
        )
        data_set = response['ResultsByTime'][0]['Groups']
        for data_point in data_set:
            account_id = data_point['Keys'][0]
            cost = data_point['Metrics']['UnblendedCost']['Amount']
            if data_point['Metrics']['UnblendedCost']['Unit'] != "USD":
                logger.warning(f"Account {account_id} has costs in non-USD: {data_point['Metrics']['UnblendedCost']['Unit']}")

            target_account = AWSAccount(account_id, config=antiope_config)
            target_account.update_attribute("last_month_cost", cost)

        # Now get Month-to-date
        response = ce_client.get_cost_and_usage(
            TimePeriod={'Start': str(start_of_this_month), 'End': str(today) },
            Metrics=['UnblendedCost'],
            Granularity='MONTHLY',
            GroupBy=[{'Type': 'DIMENSION', 'Key': 'LINKED_ACCOUNT'}],
        )
        data_set = response['ResultsByTime'][0]['Groups']
        for data_point in data_set:
            account_id = data_point['Keys'][0]
            cost = data_point['Metrics']['UnblendedCost']['Amount']
            if data_point['Metrics']['UnblendedCost']['Unit'] != "USD":
                logger.warning(f"Account {account_id} has costs in non-USD: {data_point['Metrics']['UnblendedCost']['Unit']}")
            target_account = AWSAccount(account_id, config=antiope_config)
            target_account.update_attribute("month_to_date_cost", cost)

    except AntiopeAssumeRoleError as e:
        logger.error("Unable to assume role into account {}({})".format(delegated_account.account_name, delegated_account.account_id))
        return()
    except AntiopeAssumeRoleError as e:
        logger.error("Unable to assume role into account {}({})".format(delegated_account.account_name, delegated_account.account_id))
        return()
    except ClientError as e:
        if e.response['Error']['Code'] == 'AccessDeniedException':
            logger.error(f"AccessDeniedException for access-analyzer in {delegated_account.account_name}({delegated_account.account_id})")
            return()
        else:
            logger.critical("AWS Error getting info for {}: {}".format(message['payer_id'], e))
            capture_error(message, context, e, "ClientError for {}: {}".format(message['payer_id'], e))
            raise
    except Exception as e:
        # logger.critical("{}\nMessage: {}\nContext: {}".format(e, message, vars(context)))
        # capture_error(message, context, e, "General Exception for {}: {}".format(message['payer_id'], e))
        raise


if __name__ == '__main__':


    # Logging idea stolen from: https://docs.python.org/3/howto/logging.html#configuring-logging
    # create console handler and set level to debug
    ch = logging.StreamHandler()

    logger.setLevel(logging.DEBUG)

    # create formatter
    # formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    formatter = logging.Formatter(f"%(levelname)s - %(message)s")
    # add formatter to ch
    ch.setFormatter(formatter)
    # add ch to logger
    logger.addHandler(ch)

    # # Sanity check region
    # if args.region:
    #     os.environ['AWS_DEFAULT_REGION'] = args.region

    # if 'AWS_DEFAULT_REGION' not in os.environ:
    #     logger.error("AWS_DEFAULT_REGION Not set. Aborting...")
    #     exit(1)

    try:
        lambda_handler({}, {})
    except KeyboardInterrupt:
        exit(1)