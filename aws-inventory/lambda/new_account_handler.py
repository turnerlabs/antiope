
import boto3
from botocore.exceptions import ClientError

import json
import os
import time
import datetime
from dateutil import tz

from lib.account import *
from lib.common import *

import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)

def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))

    for record in event['Records']:
        if record['eventSource'] != "aws:dynamodb":
            next
        if record['eventName'] == "INSERT":
            ddb_record = record['dynamodb']['NewImage']
            account_id = ddb_record['account_id']['S']
            account_type = ddb_record['account_status']['S']
            if account_type == "ACTIVE":
                send_message(ddb_record, os.environ['ACTIVE_TOPIC'])
            elif account_type == "FOREIGN":
                send_message(ddb_record, os.environ['FOREIGN_TOPIC'])

def send_message(record, topic):
    print("Sending Message: {}".format(record))
    sns_client = boto3.client('sns')
    try:
        sns_client.publish(
            TopicArn=topic,
            Subject="NewAccount",
            Message=json.dumps(record, sort_keys=True),
        )
    except ClientError as e:
        logger.error('Error publishing message: {}'.format(e))
