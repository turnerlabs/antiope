import boto3
from botocore.exceptions import ClientError
import json
import os
import time
import datetime
from mako.template import Template

from antiope.foreign_aws_account import *
from antiope.aws_account import *
from common import *

import logging
logger = logging.getLogger()
logger.setLevel(getattr(logging, os.getenv('LOG_LEVEL', default='INFO')))
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

assume_role_link = "<a href=\"https://signin.aws.amazon.com/switchrole?account={}&roleName={}&displayName={}\">{}</a>"


# Lambda main routine
def handler(event, context):
    logger.info("Received event: " + json.dumps(event, sort_keys=True))

    # We will make a HTML Table and a Json file with this data

    json_data = []

    # Cache account_name for all the parent accounts
    payers = {}

    # Data to be saved to S3 and used to generate the template report
    json_data = {"accounts": []}

    # Get and then sort the list of accounts by name, case insensitive.
    active_accounts = get_foreign_accounts()
    active_accounts.sort(key=lambda x: x.account_name.lower())

    for a in active_accounts:
        logger.info(a.account_name)

        # We don't want to save the entire object's attributes.
        j = a.db_record.copy()
        if 'ami_source' not in j:
            j['ami_source'] = False

        # Build the cross account role link
        json_data['accounts'].append(j)

    json_data['timestamp'] = datetime.datetime.now()
    json_data['account_count'] = len(active_accounts)
    json_data['bucket'] = os.environ['INVENTORY_BUCKET']

    # Render the Webpage
    fh = open("html_templates/foreign_inventory.html", "r")
    mako_body = fh.read()
    result = Template(mako_body).render(**json_data)

    # Save HTML and json to S3
    s3_client = boto3.client('s3')
    try:
        response = s3_client.put_object(
            # ACL='public-read',
            Body=result,
            Bucket=os.environ['INVENTORY_BUCKET'],
            ContentType='text/html',
            Key='Reports/foreign_inventory.html',
        )

        # Save the JSON to S3
        response = s3_client.put_object(
            # ACL='public-read',
            Body=json.dumps(json_data, sort_keys=True, indent=2, default=str),
            Bucket=os.environ['INVENTORY_BUCKET'],
            ContentType='application/json',
            Key='Reports/foreign_inventory.json',
        )
    except ClientError as e:
        logger.error("ClientError saving report: {}".format(e))
        raise

    return(event)
