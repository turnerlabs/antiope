
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
        health_client = target_account.get_client('health')

        data = {}

        arn_list = []
        try:
            response = health_client.describe_events(filter={ 'eventStatusCodes': [ 'upcoming' ], 'eventTypeCodes': ['AWS_EC2_INSTANCE_REBOOT_MAINTENANCE_SCHEDULED']})
            for e in response['events']:
                arn_list.append(e['arn'])

            logger.info("Got {} events for account {}".format(len(arn_list), target_account.account_name))

            if len(arn_list) != 0:
                response = health_client.describe_event_details(eventArns=arn_list)
                data['details'] = response['successfulSet']

                response = health_client.describe_affected_entities(filter={'eventArns': arn_list })
                data['entities'] = response['entities']
        except ClientError as e:
            if e.response['Error']['Code'] == 'SubscriptionRequiredException':
                msg = "{}({}) does not have Enterprise subscription".format(target_account.account_name, target_account.account_id)
                data['error'] = msg
                logger.error(msg)

        s3client = boto3.client('s3')
        s3response = s3client.put_object(
            ACL='public-read', #FIXME
            Body=json.dumps(data, sort_keys=True, default=str, indent=2),
            Bucket=os.environ['INVENTORY_BUCKET'],
            ContentType='application/json',
            Key="Health/{}.json".format(target_account.account_id),
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







def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))