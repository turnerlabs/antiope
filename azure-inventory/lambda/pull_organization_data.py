import boto3
from botocore.exceptions import ClientError

from azure_lib.common import *
from azure.mgmt.subscription import SubscriptionClient

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

    # subscription_list = get_subcriptions(credential_info)

    creds = return_azure_creds(credential_info["application_id"], credential_info["key"], credential_info["tenant_id"])

    resource_client = SubscriptionClient(creds)

    collected_subs = []
    for subscription in resource_client.subscriptions.list():

        subscription_dict = {"subscription_id": subscription.subscription_id,
                                 "display_name": subscription.display_name, "state": str(subscription.state)}

        create_or_update_subscription(subscription_dict, subscription_table)
        collected_subs.append(subscription_dict)

    if collected_subs is None:
        raise Exception("No Subscriptions found. Aborting...")

    event['subscription_list'] = collected_subs
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