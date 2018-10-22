import boto3
from botocore.exceptions import ClientError

import json
import os
import time
import datetime

from lib.account import *
from lib.common import *

import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)


# table_format = {
#     "account_id": "Account ID",
#     "account_name": "Account Name",
#     "payer_name": "Parent",
#     "root_email": "Root Address",
#     "assume_role_link": "Assume Role Link"
# }


table_format = ["account_id", "account_name", "payer_name", "root_email", "assume_role_link" ]

assume_role_link = "<a href=\"https://signin.aws.amazon.com/switchrole?account={}&roleName={}&displayName={}\">{}</a>"

# Lambda main routine
def handler(event, context):
    logger.info("Received event: " + json.dumps(event, sort_keys=True))

    dynamodb = boto3.resource('dynamodb')
    account_table = dynamodb.Table(os.environ['ACCOUNT_TABLE'])


    # We will make a HTML Table and a Json file with this data
    table_data = ""
    json_data = []

    # Cache account_name for all the parent accounts
    payers = {}

    # Get and then sort the list of accounts by name, case insensitive.
    active_accounts = get_active_accounts()
    active_accounts.sort(key=lambda x: x.account_name.lower())

    for a in active_accounts:
        logger.info(a.account_name)

        try:
            if str(a.payer_id) in payers:
                a.payer_name = payers[str(a.payer_id)]
            else:
                payer = AWSAccount(str(a.payer_id))
                a.payer_name = payer.account_name
                payers[payer.account_id] = payer.account_name
        except AccountLookupError:
            a.payer_name = "Not Found"

        # Build the cross account role link
        a.assume_role_link = assume_role_link.format(a.account_id, os.environ['ROLE_NAME'], a.account_name, os.environ['ROLE_NAME'])


        j = {}
        table_data += "<tr>"
        for col_name in table_format:
            table_data += "<td>{}</td>".format(getattr(a, col_name))
            j[col_name] = getattr(a, col_name)
        table_data += "</tr>\n"
        json_data.append(j)


    s3_client = boto3.client('s3')

    try:
        response = s3_client.get_object(
            Bucket=os.environ['INVENTORY_BUCKET'],
            Key='Templates/account_inventory.html'
        )
        html_body = str(response['Body'].read().decode("utf-8") )
    except ClientError as e:
        logger.error("ClientError getting HTML Template: {}".format(e))
        raise

    # This assumes only three {} in the template
    try:
        file = html_body.format(len(active_accounts), table_data, datetime.datetime.now())
    except Exception as e:
        logger.error("Error generating HTML Report. Template correct? : {}".format(e))
        raise


    try:
        response = s3_client.put_object(
            # ACL='public-read',
            Body=file,
            Bucket=os.environ['INVENTORY_BUCKET'],
            ContentType='text/html',
            Key='Reports/account_inventory.html',
        )

        # Save the JSON to S3
        response = s3_client.put_object(
            # ACL='public-read',
            Body=json.dumps(json_data, sort_keys=True, indent=2),
            Bucket=os.environ['INVENTORY_BUCKET'],
            ContentType='application/json',
            Key='Reports/account_inventory.json',
        )
    except ClientError as e:
        logger.error("ClientError saving report: {}".format(e))
        raise

    return(event)