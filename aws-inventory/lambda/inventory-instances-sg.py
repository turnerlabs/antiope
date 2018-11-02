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
logger.setLevel(logging.INFO)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)

INSTANCE_RESOURCE_PATH = "ec2/instance"
SG_RESOURCE_PATH = "ec2/securitygroup"

def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:

        target_account = AWSAccount(message['account_id'])
        s3_client = boto3.client('s3')

        regions = target_account.get_regions()
        if 'region' in message:
            regions = [ message['region'] ]

        # describe ec2 instances
        for r in regions:
            ec2_client = target_account.get_client('ec2', region=r)
            instance_reservations = ec2_client.describe_instances()['Reservations']
            logger.info("Found {} instance reservations for {} in {}".format(len(instance_reservations), message['account_id'], r))

            # dump info about instances to S3 as json
            for reservation in instance_reservations:
                for instance in reservation['Instances']:
                    instance['account_id'] = message['account_id']
                    instance['region'] = r
                    instance['resource_type'] = "ec2-instance"
                    save_resource_to_s3(INSTANCE_RESOURCE_PATH, instance['InstanceId'], instance)

            # describe ec2 security groups

            sec_groups = ec2_client.describe_security_groups()['SecurityGroups']
            logger.info("Found {} security groups for {} in {}".format(len(sec_groups), message['account_id'], r))

            # dump info about security groups to S3 as json
            for sec_group in sec_groups:
                sec_group['account_id'] = message['account_id']
                sec_group['region'] = r
                sec_group['resource_type'] = "ec2-sg"
                save_resource_to_s3(SG_RESOURCE_PATH, sec_group['GroupId'], sec_group)

    except AssumeRoleError as e:
        logger.error("Unable to assume role into account {}({})".format(target_account.account_name, target_account.account_id))
        return()
    except ClientError as e:
        logger.error("AWS Error getting info for {}: {}".format(target_account.account_name, e))
        return()
    except Exception as e:
        logger.error("{}\nMessage: {}\nContext: {}".format(e, message, vars(context)))
        raise