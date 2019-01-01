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

    for record in event['Records']:
        message = json.loads(record['body'])
        logger.debug("message: {}".format(json.dumps(message, sort_keys=True)))
        if 'Records' not in message:
            continue

        logger.info(f"Processing {len(message['Records'])} objects for ingestion ")
        for s3_record in message['Records']:
            bucket=s3_record['s3']['bucket']['name']
            obj_key=s3_record['s3']['object']['key']

            resource_to_index = get_object(bucket, obj_key)
            if resource_to_index is None:
                continue

            try:
                key_parts = obj_key.split("/")
                # The Elastic Search document id, is the object_name minus the file suffix
                es_id = key_parts.pop().replace(".json", "")

                # The Elastic Search Index is the remaining object prefix, all lowercase with the "/" replaced by "_"
                index = "_".join(key_parts).lower()

                # And now we build the ES URL to post to.
                url = "{}/{}/{}/{}".format(host, index, es_type, es_id)

                # Now index the document
                r = requests.post(url, auth=awsauth, json=resource_to_index, headers=headers)

                if not r.ok:
                    body = r.json()
                    if 'error' in body:
                        if body['error']['type'] == "mapper_parsing_exception":
                            new_resource_to_index = fix_principal(resource_to_index)
                            r2 = requests.post(url, auth=awsauth, json=new_resource_to_index, headers=headers)
                            if not r2.ok:
                                logger.critical(f"Failed to index {url} / {new_resource_to_index} after the principal replacement hack")
                                continue
                        else:
                            logger.error(f"Object: {obj_key} Error: {body['error']['type']} Message: {body['error']['reason']}")
                    else:
                        logger.error("Unable to Index s3://{}/{}. ES returned non-ok error: {}: {}".format(bucket, obj_key, status, body))

            except Exception as e:
                logger.critical("General Exception Indexing s3://{}/{}: {}".format(bucket, obj_key, e))
                raise


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
    """

    string_to_match = '"Principal": "*"'
    string_to_sub = '"Principal": { "ALL": "*"}'

    # Convert to String
    json_string = json.dumps(json_doc)

    print(f"In fix principal, json_string is {json_string}")

    # Do the replace
    modified_json_string = json_string.replace(string_to_match, string_to_sub)

    # Convert back to dict
    modified_json_doc = json.loads(modified_json_string)

    return(modified_json_doc)



def get_object(bucket, obj_key):
    s3 = boto3.client('s3')
    try:
        response = s3.get_object(
            Bucket=bucket,
            Key=obj_key
        )
        return(json.loads(response['Body'].read()))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            logger.error("Unable to find resource s3://{}/{}".format(bucket, obj_key))
        else:
            logger.error("Error getting resource s3://{}/{}: {}".format(bucket, obj_key, e))
        return(None)

