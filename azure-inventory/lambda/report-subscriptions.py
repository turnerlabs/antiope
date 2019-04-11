import boto3
from botocore.exceptions import ClientError

import json
import os
import time
import datetime

from azure_lib.subscription import *
from azure_lib.common import *

import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)


# table_format = {
#   "cost": 38,
#   "display_name": "azure-acocount",
#   "state": "SubscriptionState.enabled",
#   "subscription_id": "blahblah-blah-blah-blah-blahblahBlah"
# }


table_format = ["display_name", "subscription_id", "cost", "state" ]


# Lambda main routine
def handler(event, context):
    logger.info("Received event: " + json.dumps(event, sort_keys=True))

    dynamodb = boto3.resource('dynamodb')
    account_table = dynamodb.Table(os.environ['SUBSCRIPTION_TABLE'])


    # We will make a HTML Table and a Json file with this data
    table_data = ""
    json_data = []

    # Get and then sort the list of subscriptions by name, case insensitive.
    subscription_list = get_active_subscriptions()
    subscription_list.sort(key=lambda x: x.subscription_id.lower())

    for subscription in subscription_list:
        logger.info(f"{subscription.subscription_id}")

        j = {}
        table_data += "<tr>"
        for col_name in table_format:
            table_data += "<td>{}</td>".format(getattr(subscription, col_name))
            j[col_name] = getattr(subscription, col_name)
        table_data += "</tr>\n"
        json_data.append(j)


    s3_client = boto3.client('s3')

    try:
        response = s3_client.get_object(
            Bucket=os.environ['INVENTORY_BUCKET'],
            Key='Templates/subscription_inventory.html'
        )
        html_body = str(response['Body'].read().decode("utf-8") )
    except ClientError as e:
        logger.error("ClientError getting HTML Template: {}".format(e))
        raise

    # This assumes only three {} in the template
    try:
        file = html_body.format(os.environ['INVENTORY_BUCKET'], len(subscription_list), table_data, datetime.datetime.now())
    except Exception as e:
        logger.error("Error generating HTML Report. Template correct? : {}".format(e))
        raise


    try:
        response = s3_client.put_object(
            # ACL='public-read',
            Body=file,
            Bucket=os.environ['INVENTORY_BUCKET'],
            ContentType='text/html',
            Key='Reports/azure_subscription_inventory.html',
        )

        # Save the JSON to S3
        response = s3_client.put_object(
            # ACL='public-read',
            Body=json.dumps(json_data, sort_keys=True, indent=2),
            Bucket=os.environ['INVENTORY_BUCKET'],
            ContentType='application/json',
            Key='Reports/azure_subscription_inventory.json',
        )
    except ClientError as e:
        logger.error("ClientError saving report: {}".format(e))
        raise

    return(event)