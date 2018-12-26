import boto3
import re
import requests
from requests_aws4auth import AWS4Auth

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


# Lambda execution starts here
def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))

    region = os.environ['AWS_REGION']
    service = 'es'
    credentials = boto3.Session().get_credentials()
    awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, service, session_token=credentials.token)

    host = "https://{}".format(os.environ['ES_DOMAIN_ENDPOINT'])
    es_type = "_doc" # This is what es is moving to after deprecating types in 6.0

    headers = { "Content-Type": "application/json" }

    s3 = boto3.client('s3')

    for record in event['Records']:
        message = json.loads(record['body'])
        logger.debug("message: {}".format(json.dumps(message, sort_keys=True)))
        if 'Records' not in message:
            continue

        logger.info(f"Processing {len(message['Records'])} objects for ingestion ")
        for s3_record in message['Records']:
            bucket=s3_record['s3']['bucket']['name']
            obj_key=s3_record['s3']['object']['key']
            try:
                response = s3.get_object(
                    Bucket=bucket,
                    Key=obj_key
                )
                resource_to_index = json.loads(response['Body'].read())
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchKey':
                    logger.error("Unable to find resource s3://{}/{}".format(bucket, obj_key))
                else:
                    logger.error("Error getting resource s3://{}/{}: {}".format(bucket, obj_key, e))
                continue

            try:
                key_parts = obj_key.split("/")
                es_id = key_parts.pop().replace(".json", "")
                index = "_".join(key_parts).lower()
                url = "{}/{}/{}/{}".format(host, index, es_type, es_id)
                r = requests.post(url, auth=awsauth, json=resource_to_index, headers=headers)
                if not r.ok:
                    logger.error("Unable to Index s3://{}/{}. ES returned non-ok error: {}: {}".format(bucket, obj_key, r.reason, r.text))
            except Exception as e:
                logger.error("General Exception Indexing s3://{}/{}: {}".format(bucket, obj_key, e))
                raise


