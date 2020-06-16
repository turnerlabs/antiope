
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.types import TypeDeserializer
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


def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))

    try:
        for record in event['Records']:
            if record['eventSource'] != "aws:dynamodb":
                next
            if record['eventName'] == "INSERT":
                ddb_record = record['dynamodb']['NewImage']
                logger.debug(ddb_record)
                account_id = ddb_record['account_id']['S']
                account_type = ddb_record['account_status']['S']
                json_record = deseralize(ddb_record)
                if account_type == "ACTIVE":
                    send_message(json_record, os.environ['ACTIVE_TOPIC'])
                elif account_type == "FOREIGN":
                    send_message(json_record, os.environ['FOREIGN_TOPIC'])
    except ClientError as e:
        logger.critical("AWS Error for {}: {}".format(account_id, e))
        capture_error(event, context, e, f"ClientError for {account_id}")
        raise
    except Exception as e:
        logger.critical("{}\nMessage: {}\nContext: {}".format(e, event, vars(context)))
        capture_error(event, context, e, f"General Exception for {account_id}")
        raise



def send_message(record, topic):
    print("Sending Message: {}".format(record))
    sns_client = boto3.client('sns')
    try:
        sns_client.publish(
            TopicArn=topic,
            Subject="NewAccount",
            Message=json.dumps(record, sort_keys=True, default=str),
        )
    except ClientError as e:
        logger.error('Error publishing message: {}'.format(e))


def deseralize(ddb_record):
    # This is probablt a semi-dangerous hack.
    # https://github.com/boto/boto3/blob/e353ecc219497438b955781988ce7f5cf7efae25/boto3/dynamodb/types.py#L233
    ds = TypeDeserializer()
    output = {}
    for k, v in ddb_record.items():
        output[k] = ds.deserialize(v)
    return(output)
