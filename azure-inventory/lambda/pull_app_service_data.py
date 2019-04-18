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

    subsricption_list = get_subcriptions(credential_info)
    if subsricption_list is None:
        raise Exception("No Projects found. Aborting...")

    for subsricption in subsricption_list:

        web_site_list = get_web_sites(credential_info, subsricption["subscription_id"])
        if web_site_list is not None:
            for web_site in web_site_list:
                logger.info(web_site)

            for web_site in web_site_list:
                cleaned_website_id = web_site["id"].replace("/", "-")
                save_resource_to_s3("app_service", cleaned_website_id, web_site)