import json
import os

import json


from msrestazure.azure_active_directory import ServicePrincipalCredentials
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.consumption import ConsumptionManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.subscription import SubscriptionClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.web import WebSiteManagementClient
from azure.mgmt.sql import SqlManagementClient
from azure.mgmt.datafactory import DataFactoryManagementClient
from azure.mgmt.keyvault import KeyVaultManagementClient
from azure.mgmt.logic import LogicManagementClient
from azure.mgmt.resource import ResourceManagementClient


import boto3
from botocore.exceptions import ClientError
from .subscription import AzureSubscription

import logging
logger = logging.getLogger()
logger.setLevel(logging.ERROR)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)



def safe_dump_json(obj)->dict:
    """
    Converts an object to a json in a shallow way
    :param obj:
    :return:
    """
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
    """
    This function saves a json file to s3
    :param prefix: like VM, APP-SERVICE
    :param resource_id: the id of the resource often Azure uses slashes \ but we turn them into -
    :param resource: the json of the resources
    :return: Nothing
    """
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
    """
    This function returns credential object to be utilized in the Azure SDK clients. There are multiple ways for authentication
    :param app_id:
    :param key:
    :param tenant_id:
    :return:
    """
    return ServicePrincipalCredentials(
        client_id=app_id,
        secret=key,
        tenant=tenant_id
    )


def get_cost(azure_creds, subscription_id):
    """
    This function returns the overall cost of a subscription.
    :param azure_creds: The cred json that we keep in AWS Key Vault
    :param subscription_id: the id of the subscription
    :return:
    """

    creds = return_azure_creds(azure_creds["application_id"], azure_creds["key"], azure_creds["tenant_id"])

    consumption_client = ConsumptionManagementClient(creds, subscription_id, base_url=None)
    sum = 0
    for uu in consumption_client.usage_details.list():
        sum += uu.pretax_cost

    return int(sum)


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
    """
    Returns the public ip addresses that the subscription has
    :param azure_creds:
    :param subscription_id:
    :return:
    """
    creds = return_azure_creds(azure_creds["application_id"], azure_creds["key"], azure_creds["tenant_id"])

    network_management_client = NetworkManagementClient(creds, subscription_id)

    public_ip_addresses = []
    for ip in network_management_client.public_ip_addresses.list_all():
        public_ip_addresses.append(safe_dump_json(ip))

    return public_ip_addresses


def get_vms(azure_creds, subscription_id):
    """
    Returns the VMs that the subscription has
    :param azure_creds:
    :param subscription_id:
    :return:
    """

    creds = return_azure_creds(azure_creds["application_id"], azure_creds["key"], azure_creds["tenant_id"])

    compute_management_client = ComputeManagementClient(creds, subscription_id)

    vm_list = []
    for m in compute_management_client.virtual_machines.list_all():
        vm_list.append(safe_dump_json(m))

    return vm_list


def get_disks(azure_creds, subscription_id):
    creds = return_azure_creds(azure_creds["application_id"], azure_creds["key"], azure_creds["tenant_id"])

    compute_management_client = ComputeManagementClient(creds, subscription_id)
    
    return _generic_json_list_return(compute_management_client.disks.list())

def get_sql_servers(azure_creds, subscription_id):

    creds = return_azure_creds(azure_creds["application_id"], azure_creds["key"], azure_creds["tenant_id"])
    sql_server_resource_client = SqlManagementClient(creds, subscription_id)

    resource_source_client = ResourceManagementClient(creds,subscription_id)

    return _generic_json_list_return(sql_server_resource_client.servers.list())


def get_data_factories(azure_creds, subscription_id):

    creds = return_azure_creds(azure_creds["application_id"], azure_creds["key"], azure_creds["tenant_id"])

    data_factory_client = DataFactoryManagementClient(creds,subscription_id)

    return _generic_json_list_return(data_factory_client.factories.list())

def get_key_vaults(azure_creds, subscription_id):
    creds = return_azure_creds(azure_creds["application_id"], azure_creds["key"], azure_creds["tenant_id"])

    key_vault_client = KeyVaultManagementClient(creds, subscription_id)
    
    return _generic_json_list_return(key_vault_client.vaults.list())

def get_logic_apps(azure_creds, subscription_id):
    """
    Returns logic applications under a subscription
    :param azure_creds:
    :param subscription_id:
    :return:
    """
    creds = return_azure_creds(azure_creds["application_id"], azure_creds["key"], azure_creds["tenant_id"])

    logic_app_client = LogicManagementClient(creds, subscription_id)

    return _generic_json_list_return(logic_app_client.list_operations())

    
def _generic_json_list_return(object_list)-> list:
    """
    This function is used to convert objects into simple jsons, the sdk returns objects and we need them as jsons
    :param object_list:
    :return:
    """
    return_list = []
    for m in object_list:
        return_list.append(safe_dump_json(m))

    return return_list
    

def get_storage_accounts(azure_creds, subscription_id):

    creds = return_azure_creds(azure_creds["application_id"], azure_creds["key"], azure_creds["tenant_id"])

    storage_client = StorageManagementClient(creds, subscription_id)

    storage_list = []
    for ss in storage_client.storage_accounts.list():
        storage_list.append(safe_dump_json(ss))

    return storage_list


def get_web_sites(azure_creds, subscription_id):
    """
    This function returns the App Service resources that are used in the subscription, It is called Website in sdk, but
    App Service in the doc.
    :param azure_creds:
    :param subscription_id:
    :return:
    """

    creds = return_azure_creds(azure_creds["application_id"], azure_creds["key"], azure_creds["tenant_id"])

    web_client = WebSiteManagementClient(creds, subscription_id)

    website_list = []
    for website in web_client.web_apps.list():
        website_list.append(safe_dump_json(website))

    return website_list

