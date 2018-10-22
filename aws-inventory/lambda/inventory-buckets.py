
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
logger.setLevel(logging.DEBUG)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)

RESOURCE_PATH = "s3/bucket"

def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        discover_buckets(target_account)

    except AssumeRoleError as e:
        logger.error("Unable to assume role into account {}({})".format(target_account.account_name, target_account.account_id))
        return()
    except ClientError as e:
        logger.error("AWS Error getting info for {}: {}".format(target_account.account_name, e))
        return()
    except Exception as e:
        logger.error("{}\nMessage: {}\nContext: {}".format(e, message, vars(context)))
        raise

def discover_buckets(account):
    '''
        Gathers all the S3 Buckets and various details about them
    '''
    bucket_list = []

    # Not all Public IPs are attached to instances. So we use ec2 describe_network_interfaces()
    # All results are saved to S3. Public IPs and metadata go to DDB (based on the the presense of PublicIp in the Association)
    s3_client = account.get_client('s3')
    response = s3_client.list_buckets() # This API call doesn't paganate. Go fig...
    bucket_list += response['Buckets']

    for b in bucket_list:

        bucket_name = b['Name']

        # Decorate with the account info
        b['account_id']       = account.account_id
        b['account_name']     = account.account_name
        b['last_updated']     = str(datetime.datetime.now(tz.gettz('US/Eastern')))
        b['errors'] = {}


        # Go through a bunch of API calls to get details on this bucket
        try:
            response = s3_client.get_bucket_encryption(Bucket=bucket_name)
            if 'ServerSideEncryptionConfiguration' in response:
                b['ServerSideEncryptionConfiguration'] = response['ServerSideEncryptionConfiguration']
        except ClientError as e:
            if e.response['Error']['Code'] != 'ServerSideEncryptionConfigurationNotFoundError':
                b['errors']['ServerSideEncryptionConfiguration'] = e

        try:
            response = s3_client.get_bucket_acl(Bucket=bucket_name)
            if 'Grants' in response:
                b['Grants'] = response['Grants']
        except ClientError as e:
            b['errors']['Grants'] = e

        try:
            response = s3_client.get_bucket_location(Bucket=bucket_name)
            if 'LocationConstraint' in response:
                if response['LocationConstraint'] is None:
                    b['Location'] = "us-east-1"
                else:
                    b['Location'] = response['LocationConstraint']
        except ClientError as e:
            b['errors']['Location'] = e

        try:
            response = s3_client.get_bucket_policy(Bucket=bucket_name)
            if 'Policy' in response:
                b['BucketPolicy'] = json.loads(response['Policy'])
        except ClientError as e:
            if e.response['Error']['Code'] != 'NoSuchBucketPolicy':
                b['errors']['BucketPolicy'] = e

        try:
            response = s3_client.get_bucket_tagging(Bucket=bucket_name)
            if 'TagSet' in response:
                b['TagSet'] = response['TagSet']
        except ClientError as e:
            if e.response['Error']['Code'] != 'NoSuchTagSet':
                b['errors']['TagSet'] = e

        try:
            response = s3_client.get_bucket_versioning(Bucket=bucket_name)
            del response['ResponseMetadata']
            b['Versioning'] = response
        except ClientError as e:
            b['errors']['Versioning'] = e

        try:
            response = s3_client.get_bucket_request_payment(Bucket=bucket_name)
            del response['ResponseMetadata']
            b['RequestPayer'] = response
        except ClientError as e:
            b['errors']['RequestPayer'] = e

        try:
            response = s3_client.get_bucket_website(Bucket=bucket_name)
            del response['ResponseMetadata']
            b['Website'] = response
        except ClientError as e:
            if e.response['Error']['Code'] != 'NoSuchWebsiteConfiguration':
                b['errors']['Website'] = e

        try:
            response = s3_client.get_bucket_logging(Bucket=bucket_name)
            if 'LoggingEnabled' in response:
                b['Logging'] = response['LoggingEnabled']
        except ClientError as e:
            b['errors']['Logging'] = e

        try:
            response = s3_client.get_bucket_cors(Bucket=bucket_name)
            if 'CORSRules' in response:
                b['CORSRules'] = response['CORSRules']
        except ClientError as e:
            if e.response['Error']['Code'] != 'NoSuchCORSConfiguration':
                b['errors']['CORSRules'] = e

        save_resource_to_s3(RESOURCE_PATH, bucket_name, b)



def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))