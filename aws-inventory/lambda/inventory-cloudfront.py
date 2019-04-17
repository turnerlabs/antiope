import boto3
from botocore.exceptions import ClientError

import json
import os
import time
import datetime
from dateutil import tz

from lib.account import *
from lib.common import *

import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)

RESOURCE_PATH = "cloudfront/distribution"
RESOURCE_TYPE = "AWS::CloudFront::Distribution"

def lambda_handler(event, context):
    set_debug(event, logger)
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:

        target_account = AWSAccount(message['account_id'])

        # Cloudfront is a global service
        cf_client = target_account.get_client('cloudfront')

        resource_item = {}
        resource_item['awsAccountId']                   = target_account.account_id
        resource_item['awsAccountName']                 = target_account.account_name
        resource_item['resourceType']                   = RESOURCE_TYPE
        resource_item['source']                         = "Antiope"

        for distribution in list_distributions(cf_client, target_account):

            resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
            resource_item['configuration']                  = distribution
            resource_item['supplementaryConfiguration']     = {}
            resource_item['resourceId']                     = distribution['Id']
            resource_item['resourceName']                   = distribution['DomainName']
            resource_item['ARN']                            = distribution['ARN']
            resource_item['errors']                         = {}

            save_resource_to_s3(RESOURCE_PATH, distribution['Id'], resource_item)

    except AssumeRoleError as e:
        logger.error("Unable to assume role into account {}({})".format(target_account.account_name, target_account.account_id))
        return()
    except ClientError as e:
        logger.critical("AWS Error getting info for {}: {}".format(target_account.account_name, e))
        raise
    except Exception as e:
        logger.critical("{}\nMessage: {}\nContext: {}".format(e, message, vars(context)))
        raise


def list_distributions(cf_client, target_account):
    distributions = []
    response = cf_client.list_distributions()
    while 'NextMarker' in response['DistributionList']:
        for i in response['DistributionList']['Items']:
            distributions.append(i)
        response = cf_client.list_distributions(Marker=response['NextMarker'])
    if 'Items' not in response['DistributionList']:
        return(distributions)
    for i in response['DistributionList']['Items']:
        distributions.append(i)
    return(distributions)