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

RESOURCE_PATH = "ec2/ami"
RESOURCE_TYPE = "AWS::EC2::AMI"


def lambda_handler(event, context):
    if 'debug' in event and event['debug']:
        logger.setLevel(logging.DEBUG)

    if 'DEBUG' in os.environ and os.environ['DEBUG'] == "True":
        logger.setLevel(logging.DEBUG)

    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:

        target_account = AWSAccount(message['account_id'])

        regions = target_account.get_regions()
        if 'region' in message:
            regions = [message['region']]

        # describe ec2 instances
        for r in regions:
            ec2_client = target_account.get_client('ec2', region=r)
            process_instances(target_account, ec2_client, r)

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


def process_instances(target_account, ec2_client, region):
    instance_reservations = get_all_instances(ec2_client)
    logger.debug("Found {} instance reservations for {} in {}".format(len(instance_reservations), target_account.account_id, region))

    seen_images = []
    seen_owners = []

    # dump info about instances to S3 as json
    for reservation in instance_reservations:
        for instance in reservation['Instances']:
            if instance['ImageId'] not in seen_images:
                image_id = instance['ImageId']
                owner = process_image(target_account, ec2_client, region, image_id, seen_owners)
                seen_images.append(image_id)
                seen_owners.append(owner)


def process_image(target_account, ec2_client, region, image_id, seen_owners):
    response = ec2_client.describe_images(ImageIds=[image_id])
    # dump info about instances to S3 as json
    for image in response['Images']:

        resource_item = {}
        resource_item['awsAccountId']                   = target_account.account_id
        resource_item['awsAccountName']                 = target_account.account_name
        resource_item['resourceType']                   = RESOURCE_TYPE
        resource_item['source']                         = "Antiope"
        resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
        resource_item['awsRegion']                      = region
        resource_item['configuration']                  = image
        if 'Tags' in image:
            resource_item['tags']                       = parse_tags(image['Tags'])
        resource_item['supplementaryConfiguration']     = {}
        resource_item['resourceId']                     = image['ImageId']
        resource_item['errors']                         = {}
        resource_item['resourceName']                   = image['Name']
        resource_item['resourceCreationTime']           = image['CreationDate']
        save_resource_to_s3(RESOURCE_PATH, resource_item['resourceId'], resource_item)

        if image['OwnerId'] not in seen_owners:
            process_trusted_account(image['OwnerId'])


def get_all_instances(ec2_client):
    output = []
    response = ec2_client.describe_instances()
    while 'NextToken' in response:
        output += response['Reservations']
        response = ec2_client.describe_instances(NextToken=response['NextToken'])
    output += response['Reservations']
    return(output)


def process_trusted_account(account_id):
    '''Given an AWS Principal, determine if the account is known, and if not known, add to the accounts database'''
    dynamodb = boto3.resource('dynamodb')
    account_table = dynamodb.Table(os.environ['ACCOUNT_TABLE'])

    response = account_table.get_item(
        Key={'account_id': account_id},
        AttributesToGet=['account_id', 'account_status'],
        ConsistentRead=True
    )
    if 'Item' not in response:
        logger.info(u"Adding foreign account {}".format(account_id))
        try:
            response = account_table.put_item(
                Item={
                    'account_id': account_id,
                    'account_name': "unknown",
                    'account_status': "FOREIGN",
                    'ami_source': True
                }
            )
        except ClientError as e:
            raise AccountUpdateError(u"Unable to create {}: {}".format(a[u'Name'], e))
