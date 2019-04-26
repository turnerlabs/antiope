import boto3
import json
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)


def handler(event, context):
    if 'debug' in event and event['debug']:
        logger.setLevel(logging.DEBUG)

    if 'DEBUG' in os.environ and os.environ['DEBUG'] == "True":
        logger.setLevel(logging.DEBUG)

    logger.info("Received event: " + json.dumps(event, sort_keys=True))

    client = boto3.client('sns')

    for subscription in event['subscription_list']:
        message = {}
        message['subscription_id'] = subscription["subscription_id"]  # Which account to process

        resources_available = [
            "Logic-Apps",
            "Key-Vaults",
            "Data-Factories",
            "SQL-Servers",
            "Disks",
            "Storage-Account",
            "VM",
            "App-Service",
            "IP",
            "Cost"]

        for resource in resources_available:

            message["resource"] = resource
            logger.info("Pushing Message: " + json.dumps(message, sort_keys=True))
            response = client.publish(
                TopicArn=os.environ['TRIGGER_ACCOUNT_INVENTORY_ARN'],
                Message=json.dumps(message)
            )

    return event


