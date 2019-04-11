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

    credential_info = get_azure_creds(os.environ['AZURE_SECRET_NAME'])
    if credential_info is None:
        raise Exception("Unable to extract Azure Credentials. Aborting...")

    project_list = get_subcriptions(credential_info)
    if project_list is None:
        raise Exception("No Projects found. Aborting...")

    for project in project_list:

        ip_list = get_public_ips_of_subscription(credential_info, project["subscription_id"])
        if ip_list is not None:
            for ip_info in ip_list:
                logger.info(ip_info)

            for ip_info in ip_list:
                cleaned_ip_id = ip_info["id"].replace("/", "-")
                save_resource_to_s3("ip", cleaned_ip_id, ip_info)