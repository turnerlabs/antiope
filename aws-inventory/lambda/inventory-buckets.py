
import boto3
from botocore.exceptions import ClientError

import json
import os
import time
import datetime
from dateutil import tz

from antiope.aws_account import *
from common import *

import logging
logger = logging.getLogger()
logger.setLevel(getattr(logging, os.getenv('LOG_LEVEL', default='INFO')))
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)


RESOURCE_PATH = "s3/bucket"
RESOURCE_TYPE = "AWS::S3::Bucket"


def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        discover_buckets(target_account, context)

    except AntiopeAssumeRoleError as e:
        logger.error("Unable to assume role into account {}({})".format(target_account.account_name, target_account.account_id))
        return()
    except ClientError as e:
        logger.critical("AWS Error getting info for {}: {}".format(message['account_id'], e))
        capture_error(message, context, e, "ClientError for {}: {}".format(message['account_id'], e))
        raise
    except Exception as e:
        logger.critical("{}\nMessage: {}\nContext: {}".format(e, message, vars(context)))
        capture_error(message, context, e, "General Exception for {}: {}".format(message['account_id'], e))
        raise


def discover_buckets(account, context):
    '''
        Gathers all the S3 Buckets and various details about them
    '''
    bucket_list = []

    # Not all Public IPs are attached to instances. So we use ec2 describe_network_interfaces()
    # All results are saved to S3. Public IPs and metadata go to DDB (based on the the presense of PublicIp in the Association)
    s3_client = account.get_client('s3')
    response = s3_client.list_buckets()  # This API call doesn't paganate. Go fig...
    bucket_list += response['Buckets']

    resource_item = {}
    resource_item['awsAccountId']                   = account.account_id
    resource_item['awsAccountName']                 = account.account_name
    resource_item['resourceType']                   = RESOURCE_TYPE
    resource_item['source']                         = "Antiope"

    count = 0

    for b in bucket_list:

        if context.get_remaining_time_in_millis() < 5000: # 5 second warning
            logger.critical(f"Ran out of time after {count} buckets inventoried")
            raise LambdaRunningOutOfTime(f"Time remaining: {context.get_remaining_time_in_millis()}")

        bucket_name = b['Name']

        resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
        resource_item['configuration']                  = b
        resource_item['supplementaryConfiguration']     = {}
        resource_item['resourceId']                     = b['Name']
        resource_item['resourceName']                   = b['Name']
        resource_item['ARN']                            = "arn:aws:s3:::{}".format(b['Name'])
        resource_item['resourceCreationTime']           = b['CreationDate']
        resource_item['errors']                         = {}

        # Go through a bunch of API calls to get details on this bucket
        try:
            response = s3_client.get_bucket_encryption(Bucket=bucket_name)
            if 'ServerSideEncryptionConfiguration' in response:
                resource_item['supplementaryConfiguration']['ServerSideEncryptionConfiguration'] = response['ServerSideEncryptionConfiguration']
        except ClientError as e:
            if e.response['Error']['Code'] != 'ServerSideEncryptionConfigurationNotFoundError':
                resource_item['errors']['ServerSideEncryptionConfiguration'] = e

        try:
            response = s3_client.get_bucket_acl(Bucket=bucket_name)
            if 'Grants' in response:
                resource_item['supplementaryConfiguration']['Grants'] = response['Grants']
        except ClientError as e:
            resource_item['errors']['Grants'] = e

        try:
            response = s3_client.get_bucket_location(Bucket=bucket_name)
            if 'LocationConstraint' in response:
                if response['LocationConstraint'] is None:
                    resource_item['supplementaryConfiguration']['Location'] = "us-east-1"
                    resource_item['awsRegion'] = "us-east-1"
                else:
                    resource_item['supplementaryConfiguration']['Location'] = response['LocationConstraint']
                    resource_item['awsRegion'] = response['LocationConstraint']
        except ClientError as e:
            resource_item['errors']['Location'] = e

        try:
            response = s3_client.get_bucket_policy(Bucket=bucket_name)
            if 'Policy' in response:
                resource_item['supplementaryConfiguration']['BucketPolicy'] = json.loads(response['Policy'])
        except ClientError as e:
            if e.response['Error']['Code'] != 'NoSuchBucketPolicy':
                resource_item['errors']['BucketPolicy'] = e

        try:
            response = s3_client.get_bucket_tagging(Bucket=bucket_name)
            if 'TagSet' in response:
                resource_item['tags'] = parse_tags(response['TagSet'])
        except ClientError as e:
            if e.response['Error']['Code'] != 'NoSuchTagSet':
                resource_item['errors']['TagSet'] = e

        # try:
        #     response = s3_client.get_bucket_versioning(Bucket=bucket_name)
        #     del response['ResponseMetadata']
        #     resource_item['supplementaryConfiguration']['Versioning'] = response
        # except ClientError as e:
        #     resource_item['errors']['Versioning'] = e

        # try:
        #     response = s3_client.get_bucket_request_payment(Bucket=bucket_name)
        #     del response['ResponseMetadata']
        #     resource_item['supplementaryConfiguration']['RequestPayer'] = response
        # except ClientError as e:
        #     resource_item['errors']['RequestPayer'] = e

        # try:
        #     response = s3_client.get_bucket_website(Bucket=bucket_name)
        #     del response['ResponseMetadata']
        #     resource_item['supplementaryConfiguration']['Website'] = response
        # except ClientError as e:
        #     if e.response['Error']['Code'] != 'NoSuchWebsiteConfiguration':
        #         resource_item['errors']['Website'] = e

        # try:
        #     response = s3_client.get_bucket_logging(Bucket=bucket_name)
        #     if 'LoggingEnabled' in response:
        #         resource_item['supplementaryConfiguration']['Logging'] = response['LoggingEnabled']
        # except ClientError as e:
        #     resource_item['errors']['Logging'] = e

        # try:
        #     response = s3_client.get_bucket_cors(Bucket=bucket_name)
        #     if 'CORSRules' in response:
        #         resource_item['supplementaryConfiguration']['CORSRules'] = response['CORSRules']
        # except ClientError as e:
        #     if e.response['Error']['Code'] != 'NoSuchCORSConfiguration':
        #         resource_item['errors']['CORSRules'] = e

        save_resource_to_s3(RESOURCE_PATH, resource_item['resourceId'], resource_item)
        count +=1


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))
