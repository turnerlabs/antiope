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


# Lambda main routine
def handler(event, context):
    set_debug(event, logger)

    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        dynamodb = boto3.resource('dynamodb')
        billing_table = dynamodb.Table(os.environ['BILLING_TABLE'])

        # We process the account we're told to via the SNS Message that invoked us.
        account_id = message['account_id']
        target_account = AWSAccount(account_id)

        billing_data = get_current_spend(target_account)
        if billing_data is None:
            logger.error("No billing data returned for {}".format(account_id))
            return(event)

        response = billing_table.put_item(
            Item={
                'account_id':        target_account.account_id,
                'datetime':          str(billing_data['Timestamp']),
                'estimated_charges': str(billing_data['Maximum'])
            }
        )
        logger.info("Saved new est charges of {} for {}({})".format(str(billing_data['Maximum']), target_account.account_name, target_account.account_id))

        return(event)
    except Exception as e:
        logger.error("{}\nMessage: {}\nContext: {}".format(e, message, vars(context)))
        raise
# end handler()


def get_current_spend(account):
    cwm_client = account.get_client('cloudwatch', region="us-east-1")

    try:
        response = cwm_client.get_metric_statistics(
            Namespace='AWS/Billing',
            MetricName='EstimatedCharges',
            Dimensions=[
                {
                    'Name': 'Currency',
                    'Value': 'USD'
                },
            ],
            StartTime=datetime.datetime.now() - datetime.timedelta(hours = 24),
            EndTime=datetime.datetime.now(),
            Period=21600,  # 6 hours
            Statistics=['Maximum'],
            Unit='None'
        )
        logger.debug(json.dumps(response, sort_keys=True, indent=2, default=str))
        max_point = None
        for point in response['Datapoints']:
            if max_point is None:
                max_point = point
                continue
            if point['Maximum'] > max_point['Maximum']:
                # logger.info("{} is more than {}".format(point['Maximum'], max_point['Maximum']))
                max_point = point
        return(max_point)
    except KeyError as e:
        logger.error("KeyError getting spend: {} -- Response: {}".format(e, response))
        return(None)
    except IndexError as e:
        logger.error("IndexError getting spend: {} -- Response: {}".format(e, response))
        return(None)
    except ClientError as e:
        logger.error("ClientError getting spend: {}".format(e))
        return(None)
