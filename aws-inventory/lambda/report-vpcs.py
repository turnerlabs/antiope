import boto3
from botocore.exceptions import ClientError
import json
import os
import time
import datetime
from mako.template import Template

from antiope.aws_account import *
from antiope.vpc import *
from common import *

import logging
logger = logging.getLogger()
logger.setLevel(getattr(logging, os.getenv('LOG_LEVEL', default='INFO')))
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)


# Lambda main routine
def handler(event, context):
    set_debug(event, logger)
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))

    # We will make a HTML Table and a Json file with this data
    json_data = {"vpcs": []}

    # Get and then sort the list of accounts by name, case insensitive.
    active_accounts = get_active_accounts()
    active_accounts.sort(key=lambda x: x.account_name.lower())

    for a in active_accounts:
        logger.debug(a.account_name)

        for v in a.get_vpcs():
            logger.debug(f"\tv.vpc_id")
            j = {}
            j['vpc'] = v.db_record.copy()
            j['account'] = a.db_record.copy()

            # Skip VPCs that have nothing in them
            if not hasattr(v, "instance_states"):
                continue
            if v.instance_states['running'] == 0 and v.instance_states['stopped'] == 0:
                continue

            j['instance_states'] = v.instance_states
            json_data['vpcs'].append(j)

    # Add some summary data for the Template
    json_data['timestamp'] = datetime.datetime.now()
    json_data['vpc_count'] = len(json_data['vpcs'])
    json_data['account_count'] = len(active_accounts)
    json_data['bucket'] = os.environ['INVENTORY_BUCKET']

    # Render the Webpage
    fh = open("html_templates/vpc_inventory.html", "r")
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
            Key='Reports/vpc_inventory.html',
        )

        # Save the JSON to S3
        response = s3_client.put_object(
            # ACL='public-read',
            Body=json.dumps(json_data, sort_keys=True, indent=2, default=str),
            Bucket=os.environ['INVENTORY_BUCKET'],
            ContentType='application/json',
            Key='Reports/vpc_inventory.json',
        )
    except ClientError as e:
        logger.error("ClientError saving report: {}".format(e))
        raise

    return(event)


if __name__ == '__main__':

    # Logging idea stolen from: https://docs.python.org/3/howto/logging.html#configuring-logging
    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    # create formatter
    # formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    # add formatter to ch
    ch.setFormatter(formatter)
    # add ch to logger
    logger.addHandler(ch)

    os.environ['VPC_TABLE'] = "turner-antiope-dev-aws-inventory-vpc-inventory"
    os.environ['ACCOUNT_TABLE'] = "turner-antiope-dev-aws-inventory-accounts"
    os.environ['INVENTORY_BUCKET'] = "turner-antiope-dev"
    os.environ['ROLE_NAME'] = "GTO-ISO-Audit"
    os.environ['ROLE_SESSION_NAME'] = "Antiope"

    handler({}, {})
