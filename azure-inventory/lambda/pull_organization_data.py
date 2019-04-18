import boto3
from botocore.exceptions import ClientError

from azure_lib.common import *

import json
import os
import time

import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)


# Lambda main routine
def handler(event, context):
    logger.info("Received event: " + json.dumps(event, sort_keys=True))

    dynamodb = boto3.resource('dynamodb')
    subscription_table = dynamodb.Table(os.environ['SUBSCRIPTION_TABLE'])

    credential_info = get_azure_creds(os.environ['AZURE_SECRET_NAME'])
    if credential_info is None:
        raise Exception("Unable to extract Azure Credentials. Aborting...")

    subscription_list = get_subcriptions(credential_info)
    if subscription_list is None:
        raise Exception("No Subscriptions found. Aborting...")

    # # print(subscription_list)
    # for p in subscription_list:
    #     logger.info(p)

    for p in subscription_list:
        create_or_update_subscription(p, subscription_table)

    event['subscription_list'] = subscription_list
    return(event)

# end handler()

##############################################


def create_or_update_subscription(subscription, subscription_table):
    logger.info(u"Adding subscription {}".format(subscription))

    try:
        #response = subscription_table.put_item(Item=subscription)
        # response = subscription_table.update_item(
        #     Key={'subscription_id': subscription["subscription_id"]},
        #     AttributeUpdates=subscription,
        # )
        #
        for key in subscription.keys():
            if key != "subscription_id":
                response = subscription_table.update_item(
                        Key={'subscription_id': subscription["subscription_id"]},
                    UpdateExpression='SET #ts = :val1',
                    ExpressionAttributeValues={
                        ":val1": subscription[key]
                    },
                    ExpressionAttributeNames={
                        "#ts": key
                    }
                )
    except ClientError as e:
        raise AccountUpdateError(u"Unable to create {}: {}".format(subscription, e))
    except KeyError as e:
        logger.critical(f"Subscription {subscription} is missing a key: {e}")


class AccountUpdateError(Exception):
    '''raised when an update to DynamoDB Fails'''