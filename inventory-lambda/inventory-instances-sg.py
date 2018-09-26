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
                    response = s3_client.put_object(
                        Body=json.dumps(instance, sort_keys=True, default=str, indent=2),
                        Bucket=os.environ['INVENTORY_BUCKET'],
                        ContentType='application/json',
                        Key='Resources/%s.json' % instance['InstanceId']
                    )

            # describe ec2 security groups

            sec_groups = ec2_client.describe_security_groups()['SecurityGroups']
            logger.info("Found {} security groups for {} in {}".format(len(sec_groups), message['account_id'], r))

            # dump info about security groups to S3 as json
            for sec_group in sec_groups:
                sec_group['account_id'] = message['account_id']
                sec_group['region'] = r
                response = s3_client.put_object(
                    Body=json.dumps(sec_group, sort_keys=True, default=str, indent=2),
                    Bucket=os.environ['INVENTORY_BUCKET'],
                    ContentType='application/json',
                    Key='Resources/%s.json' % sec_group['GroupId']
                )
    except AssumeRoleError as e:
        logger.error("Unable to assume role into account {}({})".format(target_account.account_name, target_account.account_id))
        return()
    except ClientError as e:
        logger.error("AWS Error getting info for {}: {}".format(target_account.account_name, e))
        return()
    except Exception as e:
        logger.error("{}\nMessage: {}\nContext: {}".format(e, message, vars(context)))
        raise