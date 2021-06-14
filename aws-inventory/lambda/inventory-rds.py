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

RDS_RESOURCE_PATH = "rds/dbinstance"
AURORA_RESOURCE_PATH = "rds/dbcluster"
RDS_TYPE = "AWS::RDS::DBInstance"
AURORA_TYPE = "AWS::RDS::DBCluster"

def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        for r in target_account.get_regions():
            try:
                discover_rds(target_account, r)
                discover_aurora(target_account, r)
            except ClientError as e:
                if e.response['Error']['Code'] == 'AccessDenied':
                    logger.warning(f"Access Denied for RDS in region {r} for account {target_account.account_name}({target_account.account_id}): {e}")
                    continue
                else:
                    raise

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


def discover_rds(account, region):
    '''Discover all Database Instances (RDS)'''

    databases = []

    rds_client = account.get_client('rds', region=region)
    response = rds_client.describe_db_instances()
    while 'Marker' in response:  # Gotta Catch 'em all!
        databases += response['DBInstances']
        response = rds_client.describe_db_instances(Marker=response['Marker'])
    databases += response['DBInstances']

    for rds in databases:
        name = rds['DBInstanceIdentifier']

        resource_item = {}
        resource_item['awsAccountId']                   = account.account_id
        resource_item['awsAccountName']                 = account.account_name
        resource_item['resourceType']                   = RDS_TYPE
        resource_item['source']                         = "Antiope"
        resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
        resource_item['awsRegion']                      = region
        resource_item['configuration']                  = rds
        resource_item['supplementaryConfiguration']     = {}
        resource_item['resourceName']                   = rds['DBInstanceIdentifier']
        resource_item['resourceId']                     = f"{account.account_id}-{region}-{rds['DBInstanceIdentifier']}"
        resource_item['ARN']                            = rds['DBInstanceArn']
        resource_item['resourceCreationTime']           = rds['InstanceCreateTime']
        resource_item['errors']                         = {}

        try:
            tags = rds_client.list_tags_for_resource(ResourceName=name)
            resource_item['tags'] = parse_tags(tags['TagList'])
        except (ClientError, KeyError, IndexError):
            pass  # If Tags aren't present or whatever, just ignore

        save_resource_to_s3(RDS_RESOURCE_PATH, resource_item['resourceId'], resource_item)

def discover_aurora(account, region):
    '''Discover all Database Instances (RDS)'''

    databases = []

    rds_client = account.get_client('rds', region=region)
    response = rds_client.describe_db_clusters()
    while 'Marker' in response:  # Gotta Catch 'em all!
        databases += response['DBClusters']
        response = rds_client.describe_db_clusters(Marker=response['Marker'])
    databases += response['DBClusters']

    for rds in databases:
        name = rds['DBClusterIdentifier']

        resource_item = {}
        resource_item['awsAccountId']                   = account.account_id
        resource_item['awsAccountName']                 = account.account_name
        resource_item['resourceType']                   = AURORA_TYPE
        resource_item['source']                         = "Antiope"
        resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
        resource_item['awsRegion']                      = region
        resource_item['configuration']                  = rds
        resource_item['supplementaryConfiguration']     = {}
        resource_item['resourceName']                   = rds['DBClusterIdentifier']
        resource_item['resourceId']                     = f"{account.account_id}-{region}-{rds['DBClusterIdentifier']}"
        resource_item['ARN']                            = rds['DBClusterArn']
        resource_item['resourceCreationTime']           = rds['ClusterCreateTime']
        resource_item['errors']                         = {}

        try:
            tags = rds_client.list_tags_for_resource(ResourceName=name)
            resource_item['tags'] = parse_tags(tags['TagList'])
        except (ClientError, KeyError, IndexError):
            pass  # If Tags aren't present or whatever, just ignore

        save_resource_to_s3(AURORA_RESOURCE_PATH, resource_item['resourceId'], resource_item)
