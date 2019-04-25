import boto3
from botocore.exceptions import ClientError

from azure_lib.common import *
from .pull_organization_data import create_or_update_subscription
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

    message = json.loads(event['Records'][0]['Sns']['Message'])

    subscription_id = message["subscription_id"]
    what_resource = message["resource"]
    write_to_s3 = True #some functions such as cost, do not write to s3, in order to make it agile we use a flag

    resources_dict = {
        "Logic-Apps": get_logic_apps,
        "Key-Vaults": get_key_vaults,
        "Data-Factories": get_data_factories,
        "SQL-Servers": get_sql_servers,
        "Disks": get_disks,
        "Storage-Account":get_storage_accounts,
        "VM":get_vms,
        "App-Service":get_web_sites,
        "IP":get_public_ips_of_subscription,
        "Cost": cost_handler
    }

    if what_resource == "cost":
        write_to_s3 = False

    resource_getter_function = resources_dict[what_resource]

    credential_info = get_azure_creds(os.environ['AZURE_SECRET_NAME'])
    if credential_info is None:
        raise Exception("Unable to extract Azure Credentials. Aborting...")

    try:
        data_list = resource_getter_function(credential_info, subscription_id)
        if write_to_s3:
            write_list_to_db(what_resource, data_list)
    except Exception as e:
        logger.exception(e)

def cost_handler(credential_info, subscription_id):
    """
    Cost handler is spesifically handled here because it writes to dynamo db table unlike the other getter methods which
    write to S3
    :param subscription_id:
    :return:
    """

    dynamodb = boto3.resource('dynamodb')
    subscription_table = dynamodb.Table(os.environ['SUBSCRIPTION_TABLE'])

    cost = get_cost(credential_info, subscription_id)

    subscription_json = {"subscription_id": subscription_id, "cost":cost}

    create_or_update_subscription(subscription_json,subscription_table)