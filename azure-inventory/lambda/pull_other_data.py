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

def write_list_to_db(tag, obj_list):
    
    if obj_list is not None:
        for obj in obj_list:
            logger.info(obj)

        for obj in obj_list:
            cleaned_obj_id = obj["id"].replace("/", "-")
            save_resource_to_s3(tag, cleaned_obj_id, obj)
    
# Lambda main routine
def handler(event, context):
    logger.info("Received event: " + json.dumps(event, sort_keys=True))

    credential_info = get_azure_creds(os.environ['AZURE_SECRET_NAME'])
    if credential_info is None:
        raise Exception("Unable to extract Azure Credentials. Aborting...")

    project_list = get_subcriptions(credential_info)
    if project_list is None:
        raise Exception("No Projects found. Aborting...")
    
    data_getters = [(get_vms, "VM"), (get_logic_apps, "Logic-Apps"), (get_key_vaults, "Key-Vaults"), (get_data_factories, "Data-Factories"), (get_sql_servers, "SQL-Servers"), (get_disks, "Disks")]
    
    for project in project_list:
        for func in data_getters:
            data_list = func[0](credential_info,project["subscription_id"])
            write_list_to_db(func[1], data_list)
            

        # vm_list = get_vms(credential_info, project["subscription_id"])
        # write_list_to_db("vm", vm_list)
        # 
        # logic_apps = get_logic_apps(credential_info, project["subscription_id"])
        # write_list_to_db("Logic-Apps", logic_apps)
        # 
        # key_vaults = get_key_vaults(credential_info, project["subscription_id"])
        # write_list_to_db("Key-Vaults", key_vaults)
        # 
        # data_factories = get_data_factories(credential_info,project["subscription_id"])
        # write_list_to_db("Data-Factories", data_factories)
        # 
        # sql_servers = get_sql_servers(credential_info,project["subscription_id"])
        # write_list_to_db("SQL-Servers", sql_servers)
        # 
        # disks = get_disks(credential_info, project["subscription_id"])
        # write_list_to_db("Disks", disks)
        