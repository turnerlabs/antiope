import boto3
from botocore.exceptions import ClientError

import json
import os
import time

import logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)

hurry_up = 800.00 # after this number of seconds, stop delaying between publish and just send the rest. We want to finish before we expire.
# TODO - have this function return unfinished work to the step function for another pass.

# Increase this number to shorten the interval between SNS Publish calls.
# The last digit of the account_id is divided by this number to create the number of seconds of delay.
accel_factor = 3

# Lambda main routine
def handler(event, context):
    if 'debug' in event and event['debug']:
        logger.setLevel(logging.DEBUG)

    if 'DEBUG' in os.environ and os.environ['DEBUG'] == "True":
        logger.setLevel(logging.DEBUG)

    logger.info("Received event: " + json.dumps(event, sort_keys=True))

    client = boto3.client('sns')

    start_time = time.time()

    for account_id in event['account_list']:

        message = event.copy()
        del(message['account_list']) # Don't need to send this along to each lamdba
        message['account_id'] = account_id # Which account to process


        # Sleep between 0 and 9 seconds before sending the message.
        if 'nowait' in event and event['nowait'] == True:
            response = client.publish(
                TopicArn=os.environ['TRIGGER_ACCOUNT_INVENTORY_ARN'],
                Message=json.dumps(message)
            )
        else:
            # if we've still got more than hurry_up time left, do the delay.
            logger.debug(f"{time.time()} - {start_time} < {hurry_up}")
            if time.time() - start_time < hurry_up:
                delay = int(message['account_id'][-1:]) / accel_factor
                logger.debug(f"Delaying {delay} sec for account {account_id}")
                time.sleep(delay)
            logger.debug(f"Publishing for {account_id}")
            response = client.publish(
                TopicArn=os.environ['TRIGGER_ACCOUNT_INVENTORY_ARN'],
                Message=json.dumps(message)
            )


    return(event)

# end handler()

##############################################


