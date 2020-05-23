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

CLUSTER_RESOURCE_PATH = "redshift/clusters"
CLUSTER_TYPE = "AWS::Redshift::Cluster"

def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        for r in target_account.get_regions():
            discover_clusters(target_account, r)

    except AntiopeAssumeRoleError as e:
        logger.error("Unable to assume role into account {}({})".format(target_account.account_name, target_account.account_id))
        return()
    except ClientError as e:
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


def discover_clusters(account, region):
    '''Discover all Database Instances (RDS)'''

    clusters = []

    client = account.get_client('redshift', region=region)
    response = client.describe_clusters()
    while 'Marker' in response:  # Gotta Catch 'em all!
        clusters += response['Clusters']
        response = client.describe_clusters(Marker=response['Marker'])
    clusters += response['Clusters']

    for c in clusters:
        name = c['ClusterIdentifier']

        resource_item = {}
        resource_item['awsAccountId']                   = account.account_id
        resource_item['awsAccountName']                 = account.account_name
        resource_item['resourceType']                   = CLUSTER_TYPE
        resource_item['source']                         = "Antiope"
        resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
        resource_item['awsRegion']                      = region
        resource_item['configuration']                  = c
        resource_item['supplementaryConfiguration']     = {}
        resource_item['resourceName']                   = c['ClusterIdentifier']
        resource_item['resourceId']                     = f"{account.account_id}-{region}-{c['ClusterIdentifier']}"
        resource_item['resourceCreationTime']           = c['ClusterCreateTime']
        resource_item['errors']                         = {}
        resource_item['tags']                           = parse_tags(c['Tags'])


        save_resource_to_s3(CLUSTER_RESOURCE_PATH, resource_item['resourceId'], resource_item)

