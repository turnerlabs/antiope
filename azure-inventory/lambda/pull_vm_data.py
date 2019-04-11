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
        
        vm_list = get_vms(credential_info, project["subscription_id"])
        if vm_list is not None:
            for vm in vm_list:
                logger.info(vm)
    
            for vm in vm_list:
                cleaned_vm_id = vm["id"].replace("/", "-")
                save_resource_to_s3("vm", cleaned_vm_id, vm)