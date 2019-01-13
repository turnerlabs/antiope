import boto3
from botocore.exceptions import ClientError

import re
import requests
from requests_aws4auth import AWS4Auth

import json
import os
import time
import datetime
from dateutil import tz

from urllib.parse import unquote

import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)


# Lambda execution starts here
def lambda_handler(event, context):
    if 'DEBUG' in os.environ and os.environ['DEBUG'] == "True":
        logger.setLevel(logging.DEBUG)
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))

    region = os.environ['AWS_REGION']
    service = 'es'
    credentials = boto3.Session().get_credentials()
    awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, service, session_token=credentials.token)

    host = "https://{}".format(os.environ['ES_DOMAIN_ENDPOINT'])
    es_type = "_doc" # This is what es is moving to after deprecating types in 6.0
    headers = { "Content-Type": "application/json" }

    # Store any object keys that weren't indexed due to the es_rejected_execution_exception error
    requeue = []

    for record in event['Records']:
        message = json.loads(record['body'])
        logger.debug("message: {}".format(json.dumps(message, sort_keys=True)))
        if 'Records' not in message:
            continue

        # If the requeue gets out of hand, this can spiral into hundreds of messages.
        if len(message['Records']) > 50:
            logger.critical(f"Skipping process of {len(message['Records'])}")
            # These get dropped on the floor
            continue

        logger.info(f"Processing {len(message['Records'])} objects for ingestion ")
        for s3_record in message['Records']:
            bucket=s3_record['s3']['bucket']['name']
            obj_key=s3_record['s3']['object']['key']

            resource_to_index = get_object(bucket, obj_key)
            if resource_to_index is None:
                continue

            # This is a shitty hack to get around the fact Principal can be "*" or {"AWS": "*"} in an IAM Statement
            modified_resource_to_index = fix_principal(resource_to_index)

            try:
                key_parts = obj_key.split("/")
                # The Elastic Search document id, is the object_name minus the file suffix
                es_id = key_parts.pop().replace(".json", "")

                # The Elastic Search Index is the remaining object prefix, all lowercase with the "/" replaced by "_"
                index = "_".join(key_parts).lower()

                # And now we build the ES URL to post to.
                url = "{}/{}/{}/{}".format(host, index, es_type, es_id)

                # Now index the document
                r = requests.post(url, auth=awsauth, json=modified_resource_to_index, headers=headers)

                logger.debug(f"{es_id} returned {r.status_code} took {r.elapsed} sec")

                if not r.ok:
                    body = r.json()
                    if 'error' in body:
                        if body['error']['type'] == "mapper_parsing_exception":
                            logger.critical(f"Principal replacement hack failed: {obj_key} / {body['error']['reason']}\n {modified_resource_to_index}")
                        elif body['error']['type'] == "es_rejected_execution_exception":
                            # This tends to be due to the thread pool being full.
                            logger.debug(f"es_rejected_execution_exception for {es_id}: {body['error']}")
                            requeue.append({ "bucket": bucket, "obj_key": obj_key})
                        else:
                            logger.error(f"Unknown Error: {body['error']['type']} Object: {obj_key} Message: {body['error']['reason']}")
                    else:
                        logger.error("Unable to Index s3://{}/{}. ES returned non-ok error: {}: {}".format(bucket, obj_key, r.status, r.text))

            except Exception as e:
                logger.critical("General Exception Indexing s3://{}/{}: {}".format(bucket, obj_key, e))
                raise

    if len(requeue) > 0:
        requeue_objects(requeue)


def fix_principal(json_doc):
    """
    WTF are we doing here? Good Question!
    ElasticSearch has an oddity where it can't handle a attribute being a literal or another level of nesting. This becomes and issue when the "Principal" in a statement
    can be one of:
        "Principal": "*" ; or
        "Principal": { "AWS": "*" } ; or
        "Principal": { "Service": "someservice.amazonaws.com" }

    You end up with an error for the first condition that states:
        'type': 'mapper_parsing_exception',
        'reason': 'object mapping for [supplementaryConfiguration.Policy.Statement.Principal] tried to parse field [Principal] as object, but found a concrete value'

    What this function will do is a total hack. It will modify the "Principal": "*" case to be "Principal": { "ALL": "*" }
    That will permit the document to be indexed and offers some level of indication as to what is happening. I hate it, but it's the best idea I've got right now.

    Note: I believe that there is a distinction between Principal: * and Principal: AWS: * - the former indicates no AWS auth is occuring at all , whereas the AWS: * means any AWS Customer (having previously authenticated to their own account). Both are bad.
    """

    string_to_match = '"Principal":"*"'
    string_to_sub = '"Principal": { "ALL": "*"}'

    # Convert to String, Make sure there are no spaces between json elements (so it can match with string_to_match)
    json_string = json.dumps(json_doc, separators=(',', ':'), indent=None)

    # print(f"In fix principal, json_string is {json_string}")

    # Do the replace
    modified_json_string = json_string.replace(string_to_match, string_to_sub)

    # Convert back to dict
    modified_json_doc = json.loads(modified_json_string)

    return(modified_json_doc)


def requeue_objects(objects):
    '''Drop any objects that were rejected because of thread issues back into the SQS queue to get ingested later'''

    sqs_client = boto3.client('sqs')
    queue_url = os.environ['SQS_QUEUE_URL']

    body = {
        'Records': []
    }

    for o in objects:
        body['Records'].append({'s3': {'bucket': {'name': o['bucket'] }, 'object': {'key': o['obj_key'] } } })

    logger.warning(f"Re-queuing {len(objects)} Objects" )
    response = sqs_client.send_message(QueueUrl=queue_url, MessageBody=json.dumps(body))
    return(len(objects))


def get_object(bucket, obj_key):
    '''get the object to index from S3 and return the parsed json'''
    s3 = boto3.client('s3')
    try:
        response = s3.get_object(
            Bucket=bucket,
            Key=unquote(obj_key)
        )
        return(json.loads(response['Body'].read()))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            logger.error("Unable to find resource s3://{}/{}".format(bucket, obj_key))
        else:
            logger.error("Error getting resource s3://{}/{}: {}".format(bucket, obj_key, e))
        return(None)

