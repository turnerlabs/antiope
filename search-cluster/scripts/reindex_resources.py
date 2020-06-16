#!/usr/bin/env python3

from dateutil import tz
from elasticsearch import Elasticsearch, RequestsHttpConnection, ElasticsearchException
from requests_aws4auth import AWS4Auth
import boto3
import datetime
import json
import os
import re
import requests
import time

import logging
logger = logging.getLogger()
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('elasticsearch').setLevel(logging.ERROR)


# This number will bang into the Lambda Timeout, so adjust with care.
BATCH_SIZE = 50

# Lambda execution starts here
def main(args, logger):

    stack_info = get_stack(args.stackname)
    bucket = get_bucket_name(stack_info)
    queue_url = get_queue_url(stack_info)

    sqs_client = boto3.client('sqs')
    s3_client = boto3.client('s3')

    counter = 0
    file_count = 0


    # Start iterating the objects
    response = s3_client.list_objects_v2(Bucket=bucket, MaxKeys=BATCH_SIZE, Prefix=args.prefix)
    while response['IsTruncated']:

        files = []
        for o in response['Contents']:
            files.append(o['Key'])
        file_count += send_message(sqs_client, queue_url, bucket, files)
        counter += 1

        response = s3_client.list_objects_v2(Bucket=bucket, MaxKeys=BATCH_SIZE, Prefix=args.prefix, ContinuationToken=response['NextContinuationToken'])

    # Do last stuff
    files = []
    for o in response['Contents']:
        files.append(o['Key'])
    file_count += send_message(sqs_client, queue_url, bucket, files)
    counter += 1

    print(f"Sent {counter} messages to index {file_count} objects")

def send_message(sqs_client, queue_url, bucket, files):

    body = {
        'Records': []
    }

    for f in files:
        body['Records'].append({'s3': {'bucket': {'name': bucket }, 'object': {'key': f } } })

    print(f"Sending {len(files)} Records to SQS" )
    response = sqs_client.send_message(QueueUrl=queue_url, MessageBody=json.dumps(body))
    # print(response)
    # print(queue_url)
    # print(json.dumps(body))
    return(len(files))


def get_bucket_name(stack_info):
    for p in stack_info['Parameters']:
        if p['ParameterKey'] == "pBucketName":
            return(p['ParameterValue'])

    # Crap, didn't find it. Better error out
    print(f"Error getting bucket name for stack {stack_info['StackName']}. Aborting... ")
    exit(1)

def get_queue_url(stack_info):
    for o in stack_info['Outputs']:
        if o['OutputKey'] == "SearchIngestEventQueueUrl":
            return(o['OutputValue'])

    # Crap, didn't find it. Better error out
    print(f"Error getting Queue URL for stack {stack_info['StackName']}. Aborting... ")
    exit(1)

def get_stack(stackname):

    cf_client = boto3.client('cloudformation')

    try:
        response = cf_client.describe_stacks(StackName=stackname)
        return(response['Stacks'][0])
    except ClientError as e:
        print(f"Failed to find CF Stack {stackname}: {e}. Aborting...")
        exit(1)
    except KeyError as e:
        print(f"Failed to find CF Stack {stackname}: {e}. Aborting...")
        exit(1)
    except IndexError as e:
        print(f"Failed to find CF Stack {stackname}: {e}. Aborting...")
        exit(1)


def do_args():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", help="print debugging info", action='store_true')
    parser.add_argument("--error", help="print error info only", action='store_true')

    parser.add_argument("--stackname", help="CF Stack with Bucket & SQS", required=True)
    parser.add_argument("--prefix", help="Re-Index resources with this prefix", required=True)

    args = parser.parse_args()

    return(args)

if __name__ == '__main__':

    args = do_args()

    # Logging idea stolen from: https://docs.python.org/3/howto/logging.html#configuring-logging
    # create console handler and set level to debug
    ch = logging.StreamHandler()
    if args.error:
        logger.setLevel(logging.ERROR)
    elif args.debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    # create formatter
    # formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    # add formatter to ch
    ch.setFormatter(formatter)
    # add ch to logger
    logger.addHandler(ch)

    main(args, logger)

