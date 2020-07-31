import json
import os
import time
import datetime
from dateutil import tz
import logging

import boto3
from botocore.exceptions import ClientError

from antiope.aws_account import *
from antiope.foreign_aws_account import *


def parse_tags(tagset):
    """Convert the tagset as returned by AWS into a normal dict of {"tagkey": "tagvalue"}"""
    output = {}
    for tag in tagset:
        output[tag['Key']] = tag['Value']
    return(output)


def save_resource_to_s3(prefix, resource_id, resource):
    """Saves the resource to S3 in prefix with the object name of resource_id.json"""
    s3client = boto3.client('s3')
    try:
        object_key = "Resources/{}/{}.json".format(prefix, resource_id)
        s3client.put_object(
            Body=json.dumps(resource, sort_keys=True, default=str, indent=2),
            Bucket=os.environ['INVENTORY_BUCKET'],
            ContentType='application/json',
            Key=object_key,
        )
    except ClientError as e:
        logger.error("Unable to save object {}: {}".format(object_key, e))


def get_active_accounts(table_name=None):
    """Returns an array of all active AWS accounts as AWSAccount objects"""

    # Reuse an AntiopeConfig object to avoid breaking on the 1024 file limit in lambda
    antiope_config = AntiopeConfig()

    account_ids = get_account_ids(status="ACTIVE", table_name=table_name)
    output = []
    for a in account_ids:
        output.append(AWSAccount(a, config=antiope_config))
    return(output)


def get_foreign_accounts():
    """Returns an array of all active AWS accounts as AWSAccount objects"""
    foreign_account_ids = get_account_ids(status="FOREIGN")
    trusted_account_ids = get_account_ids(status="TRUSTED")
    output = []
    for a in trusted_account_ids:
        output.append(ForeignAWSAccount(a))
    for a in foreign_account_ids:
        output.append(ForeignAWSAccount(a))
    return(output)


def get_account_ids(status=None, table_name=None):
    """return an array of account_ids from the Accounts table. Optionally, filter by status"""
    dynamodb = boto3.resource('dynamodb')
    if table_name:
        account_table = dynamodb.Table(table_name)
    else:
        account_table = dynamodb.Table(os.environ['ACCOUNT_TABLE'])

    account_list = []
    response = account_table.scan(
        AttributesToGet=['account_id', 'account_status']
    )
    while 'LastEvaluatedKey' in response:
        # Means that dynamoDB didn't return the full set, so ask for more.
        account_list = account_list + response['Items']
        response = account_table.scan(
            AttributesToGet=['account_id', 'account_status'],
            ExclusiveStartKey=response['LastEvaluatedKey']
        )
    account_list = account_list + response['Items']
    output = []
    for a in account_list:
        if status is None:  # Then we get everything
            output.append(a['account_id'])
        elif a['account_status'] == status:  # this is what we asked for
            output.append(a['account_id'])
        # Otherwise, don't bother.
    return(output)


def capture_error(event, context, error, message):
    '''When an exception is thrown, this function will publish a SQS message for later retrival'''
    sqs_client = boto3.client('sqs')

    queue_url = os.environ['ERROR_QUEUE']

    body = {
        'event': event,
        'function_name': context.function_name,
        'aws_request_id': context.aws_request_id,
        'log_group_name': context.log_group_name,
        'log_stream_name': context.log_stream_name,
        'error': str(error),
        'message': message
    }

    logger.info(f"Sending Lambda Exception Message: {body}")
    response = sqs_client.send_message(QueueUrl=queue_url, MessageBody=json.dumps(body))
    return(body)


def set_debug(event, logger):
    """Given the event, and using the environment, decide if the logger default should be overridden."""
    if 'debug' in event and event['debug']:
        logger.setLevel(logging.DEBUG)

    if 'DEBUG' in os.environ and os.environ['DEBUG'] == "True":
        logger.setLevel(logging.DEBUG)
    return(logger)


class LambdaRunningOutOfTime(Exception):
    '''raised by functions when the timeout is about to be hit'''

