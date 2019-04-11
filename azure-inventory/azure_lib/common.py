import json
import os

import json


from msrestazure.azure_active_directory import ServicePrincipalCredentials
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.consumption import ConsumptionManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.subscription import SubscriptionClient
from azure.mgmt.storage import StorageManagementClient



import boto3
from botocore.exceptions import ClientError
from .subscription import AzureSubscription

import logging
logger = logging.getLogger()
logger.setLevel(logging.ERROR)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)


def safe_dump_json(obj)->dict:
    # TODO needs to be able to parse json of json
    json_obj = {}
    for key in obj.__dict__.keys():
        json_obj[key] = str(obj.__dict__[key])

    return json_obj


def get_azure_creds(secret_name):
    """
    Get the azure service account key stored in AWS secrets manager.
    """

    client = boto3.client('secretsmanager')
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        logger.critical(f"Unable to get secret value for {secret_name}: {e}")
        return(None)
    else:
        if 'SecretString' in get_secret_value_response:
            secret_value = get_secret_value_response['SecretString']
        else:
            secret_value = get_secret_value_response['SecretBinary']

    try:
        secret_dict = json.loads(secret_value)
        return secret_dict
    except Exception as e:
        logger.critical(f"Error during Credential and Service extraction: {e}")
        return(None)


def save_resource_to_s3(prefix, resource_id, resource):
    s3client = boto3.client('s3')
    object_key = "Azure-Resources/{}/{}.json".format(prefix, resource_id)

    try:
        s3client.put_object(
            Body=json.dumps(resource, sort_keys=True, default=str, indent=2),
            Bucket=os.environ['INVENTORY_BUCKET'],
            ContentType='application/json',
            Key=object_key,
        )
    except ClientError as e:
        logger.error("Unable to save object {}: {}".format(object_key, e))


def return_azure_creds(app_id,key, tenant_id):
    return ServicePrincipalCredentials(
        client_id=app_id,
        secret=key,
        tenant=tenant_id
    )


def get_subcriptions(azure_creds):

    creds = return_azure_creds(azure_creds["application_id"], azure_creds["key"], azure_creds["tenant_id"])

    resource_client = SubscriptionClient(creds)

    collected_subs = []
    for subscription in resource_client.subscriptions.list():

        consumption_client = ConsumptionManagementClient(creds, subscription.subscription_id, base_url=None)
        sum = 0
        for uu in consumption_client.usage_details.list():
            sum += uu.pretax_cost

        subscription_dict = {"subscription_id": subscription.subscription_id, "display_name": subscription.display_name,
                             "cost": int(sum), "state": str(subscription.state)}


        collected_subs.append(subscription_dict)

    return collected_subs


def get_public_ips_of_subscription(azure_creds, subscription_id):
    creds = return_azure_creds(azure_creds["application_id"], azure_creds["key"], azure_creds["tenant_id"])

    network_management_client = NetworkManagementClient(creds, subscription_id)

    public_ip_addresses = []
    for ip in network_management_client.public_ip_addresses.list_all():
        public_ip_addresses.append(safe_dump_json(ip))

    return public_ip_addresses


def get_vms(azure_creds, subscription_id):

    creds = return_azure_creds(azure_creds["application_id"], azure_creds["key"], azure_creds["tenant_id"])

    compute_management_client = ComputeManagementClient(creds, subscription_id)

    vm_list = []
    for m in compute_management_client.virtual_machines.list_all():
        vm_list.append(safe_dump_json(m))

    return vm_list

def get_storage_accounts(azure_creds, subscription_id):

    creds = return_azure_creds(azure_creds["application_id"], azure_creds["key"], azure_creds["tenant_id"])

    storage_client = StorageManagementClient(creds, subscription_id)

    storage_list = []
    for ss in storage_client.storage_accounts.list():
        storage_list.append(safe_dump_json(ss))

    return storage_list
