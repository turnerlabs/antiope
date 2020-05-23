import boto3
from botocore.exceptions import ClientError
import json
import os
import time
import datetime
import csv
from antiope.aws_account import *
from common import *

import logging
logger = logging.getLogger()
logger.setLevel(getattr(logging, os.getenv('LOG_LEVEL', default='INFO')))
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

# This should match the credential report
credential_report_header = [
    "user",
    "arn",
    "user_creation_time",
    "password_enabled",
    "password_last_used",
    "password_last_changed",
    "password_next_rotation",
    "mfa_active",
    "access_key_1_active",
    "access_key_1_last_rotated",
    "access_key_1_last_used_date",
    "access_key_1_last_used_region",
    "access_key_1_last_used_service",
    "access_key_2_active",
    "access_key_2_last_rotated",
    "access_key_2_last_used_date",
    "access_key_2_last_used_region",
    "access_key_2_last_used_service",
    "cert_1_active",
    "cert_1_last_rotated",
    "cert_2_active",
    "cert_2_last_rotated"
]

prefix_header = ["account_name", "account_id", "payer_name"]


# Lambda main routine
def handler(event, context):
    set_debug(event, logger)
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))

    # Get and then sort the list of accounts by name, case insensitive.
    active_accounts = get_active_accounts()
    active_accounts.sort(key=lambda x: x.account_name.lower())

    s3_client = boto3.client('s3')

    tmp_csv = f"/tmp/CombinedCredentialReports-{event['timestamp']}.csv"
    with open(tmp_csv, 'w') as csvoutfile:
        writer = csv.writer(csvoutfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
        writer.writerow(prefix_header + credential_report_header)

        for a in active_accounts:
            logger.debug(a.account_name)

            # We will prefix all the rows in the final report with this
            account_row = [a.account_name, a.account_id, a.payer_id]

            # Pull the Credential report Antiope generated
            object_key = f"CredentialReports/{a.account_id}-{event['timestamp']}.csv"
            try:
                response = s3_client.get_object(
                    Bucket=os.environ['INVENTORY_BUCKET'],
                    Key=object_key
                )
                csv_body = str(response['Body'].read().decode("utf-8"))
                reader = csv.reader(csv_body.splitlines())
            except ClientError as e:
                logger.error(f"ClientError getting credential for {a.account_id}: {e}")
                continue

            # For each row in the report, prepend the account info and write to the final CSV
            iter_rows = iter(reader)
            next(iter_rows)  # Skip the first row
            for row in iter_rows:
                writer.writerow(account_row + row)

    csvoutfile.close()
    save_report_to_s3(event, tmp_csv)
    return(event)


def save_report_to_s3(event, tmp_csv):
    client   = boto3.client('s3')

    csvfile  = open(tmp_csv, 'rb')
    response = client.put_object(
        Body=csvfile,
        Bucket=os.environ['INVENTORY_BUCKET'],
        ContentType='text/csv',
        Key=f"CredentialReports/Combined-{event['timestamp']}.csv",
    )
    csvfile.seek(0)

    response = client.put_object(
        # ACL='public-read',
        Body=csvfile,
        Bucket=os.environ['INVENTORY_BUCKET'],
        ContentType='text/csv',
        Key='Reports/CredentialReport.csv',
    )
    csvfile.close()


if __name__ == '__main__':

    # Process Arguments
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", help="print debugging info", action='store_true')
    parser.add_argument("--error", help="print error info only", action='store_true')
    parser.add_argument("--timestamp", help="Timestamp To generate report from", required=True)

    args = parser.parse_args()

    # Logging idea stolen from: https://docs.python.org/3/howto/logging.html#configuring-logging
    # create console handler and set level to debug
    ch = logging.StreamHandler()
    if args.debug:
        ch.setLevel(logging.DEBUG)
        logging.getLogger('elasticsearch').setLevel(logging.DEBUG)
        DEBUG = True
    elif args.error:
        ch.setLevel(logging.ERROR)
    else:
        ch.setLevel(logging.INFO)

    # create formatter
    # formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    # add formatter to ch
    ch.setFormatter(formatter)
    # add ch to logger
    logger.addHandler(ch)

    os.environ['VPC_TABLE'] = "warnermedia-antiope-prod-aws-inventory-vpc-inventory"
    os.environ['ACCOUNT_TABLE'] = "warnermedia-antiope-prod-aws-inventory-accounts"
    os.environ['INVENTORY_BUCKET'] = "warnermedia-antiope"
    os.environ['ROLE_NAME'] = "wmcso-audit"
    os.environ['ROLE_SESSION_NAME'] = "Antiope"

    event = {
        'timestamp': args.timestamp
    }

    handler(event, {})
