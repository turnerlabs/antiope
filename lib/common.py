import json
import os
import time
import datetime
from dateutil import tz

import boto3
from botocore.exceptions import ClientError

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