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

        storage_list = get_storage_accounts(credential_info, project["subscription_id"])
        if storage_list is not None:
            for st in storage_list:
                logger.info(st)

            for st in storage_list:
                cleaned_st_id = st["id"].replace("/", "-")
                save_resource_to_s3("storage_account", cleaned_st_id, st)