import boto3
from botocore.exceptions import ClientError
import json
import os
import time
from datetime import datetime, timezone
from dateutil import tz

from antiope.aws_account import *
from common import *

import logging
logger = logging.getLogger()
logger.setLevel(getattr(logging, os.getenv('LOG_LEVEL', default='INFO')))
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

RESOURCE_PATH = "shield/subscription"
ATTACK_PATH = "shield/attack"
PROTECT_PATH = "shield/protection"


def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])

        # Shield Advanced is a global thing with a single subscription per account
        client = target_account.get_client('shield')

        subscription = client.describe_subscription()['Subscription']
        resource_item = {}
        resource_item['awsAccountId']                   = target_account.account_id
        resource_item['awsAccountName']                 = target_account.account_name
        resource_item['resourceType']                   = "AWS::Shield::Subscription"
        resource_item['source']                         = "Antiope"
        resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
        resource_item['configuration']                  = subscription
        resource_item['supplementaryConfiguration']     = {}
        resource_item['resourceId']                     = f"ShieldSubscription-{target_account.account_id}"
        resource_item['resourceName']                   = f"ShieldSubscription-{target_account.account_id}"
        resource_item['errors']                         = {}

        try:
            response = client.describe_emergency_contact_settings()
            if 'EmergencyContactList' in response:
                resource_item['supplementaryConfiguration']['EmergencyContactList'] = response['EmergencyContactList']
        except ClientError as e:
            message = f"Error getting emergency_contact_settings() for {target_account.account_name}: {e}"
            resource_item['errors']['EmergencyContactList'] = message
            logger.warning(message)

        try:
            response = client.describe_drt_access()
            del response['ResponseMetadata'] # Clean up the results
            resource_item['supplementaryConfiguration']['DRTAccess'] = response
        except ClientError as e:
            message = f"Error getting drt_access() for {target_account.account_name}: {e}"
            resource_item['errors']['DRTAccess'] = message
            logger.warning(message)

        save_resource_to_s3(RESOURCE_PATH, resource_item['resourceId'], resource_item)

        # List Protections
        inventory_protections(target_account, client)

        # List Attacks from the last 24 hours
        inventory_attacks(target_account, client)

    except AntiopeAssumeRoleError as e:
        logger.error("Unable to assume role into account {}({})".format(target_account.account_name, target_account.account_id))
        return()
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            logger.debug(f"Account {target_account.account_name} ({target_account.account_id}) is not subscribed to Shield Advanced")
            return(event)
        if e.response['Error']['Code'] == 'UnauthorizedOperation':
            logger.error("Antiope doesn't have proper permissions to this account")
            return(event)
        logger.critical("AWS Error getting info for {}: {}".format(message['account_id'], e))
        capture_error(message, context, e, "ClientError for {}: {}".format(message['account_id'], e))
        raise
    except Exception as e:
        logger.critical("{}\nMessage: {}\nContext: {}".format(e, message, vars(context)))
        capture_error(message, context, e, "General Exception for {}: {}".format(message['account_id'], e))
        raise

def inventory_protections(target_account, client):
    protections = []
    response = client.list_protections()
    while 'NextToken' in response:  # Gotta Catch 'em all!
        protections += response['Protections']
        response = client.list_protections(NextToken=response['NextToken'])
    protections += response['Protections']

    logger.debug(f"Discovered {len(protections)} Protections in {target_account.account_name}")

    for protection in protections:
        resource_item = {}
        resource_item['awsAccountId']                   = target_account.account_id
        resource_item['awsAccountName']                 = target_account.account_name
        resource_item['resourceType']                   = "AWS::Shield::Protection"
        resource_item['source']                         = "Antiope"
        resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
        resource_item['configuration']                  = protection
        resource_item['supplementaryConfiguration']     = {}
        resource_item['resourceId']                     = protection['Id']
        resource_item['resourceName']                   = protection['Name']
        resource_item['ARN']                            = protection['ResourceArn']
        resource_item['errors']                         = {}
        save_resource_to_s3(PROTECT_PATH, resource_item['resourceId'], resource_item)

def inventory_attacks(target_account, client):
    attacks = []
    response = client.list_attacks(StartTime={"FromInclusive":(time.time() - 86400)})
    while 'NextToken' in response:  # Gotta Catch 'em all!
        attacks += response['AttackSummaries']
        response = client.list_attacks(StartTime={"FromInclusive":(time.time() - 86400)}, NextToken=response['NextToken'])
    attacks += response['AttackSummaries']

    logger.debug(f"Discovered {len(attacks)} Attacks in {target_account.account_name}")

    for a in attacks:
        this_attack = client.describe_attack(AttackId=a['AttackId'])
        resource_item = {}
        resource_item['awsAccountId']                   = target_account.account_id
        resource_item['awsAccountName']                 = target_account.account_name
        resource_item['resourceType']                   = "AWS::Shield::Protection"
        resource_item['source']                         = "Antiope"
        resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
        resource_item['configuration']                  = this_attack
        resource_item['supplementaryConfiguration']     = {}
        resource_item['resourceId']                     = a['AttackId']
        resource_item['errors']                         = {}
        save_resource_to_s3(ATTACK_PATH, resource_item['resourceId'], resource_item)



