import json
import os
import time
import datetime
from dateutil import tz

import boto3
from botocore.exceptions import ClientError

from lib.account import *


def parse_tags(tagset):
    output = {}
    for tag in tagset:
        output[tag['Key']] = tag['Value']
    return(output)


def save_resource_to_s3(prefix, resource_id, resource):
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


def get_active_accounts():
    account_ids = get_account_ids(status="ACTIVE")
    output = []
    for a in account_ids:
        output.append(AWSAccount(a))
    return(output)



def get_account_ids(status=None):
    '''return an array of account_ids in the Accounts table. Optionally, filter by status'''
    dynamodb = boto3.resource('dynamodb')
    account_table = dynamodb.Table(os.environ['ACCOUNT_TABLE'])

    account_list = []
    response = account_table.scan(
        AttributesToGet=['account_id', 'account_status']
    )
    while 'LastEvaluatedKey' in response :
        # Means that dynamoDB didn't return the full set, so ask for more.
        account_list = account_list + response['Items']
        response = account_table.scan(
            AttributesToGet=['account_id', 'account_status'],
            ExclusiveStartKey=response['LastEvaluatedKey']
        )
    account_list = account_list + response['Items']
    output = []
    for a in account_list:
        if status is None: # Then we get everything
            output.append(a['account_id'])
        elif a['account_status'] == status: # this is what we asked for
            output.append(a['account_id'])
        # Otherwise, don't bother.
    return(output)