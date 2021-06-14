import boto3
from botocore.exceptions import ClientError, EndpointConnectionError
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

NOTBOOK_RESOURCE_PATH = "sagemaker/notebook"
NOTEBOOK_TYPE = "AWS::SageMaker::NotebookInstance"

def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        for r in target_account.get_regions():
            try:
                discover_notebooks(target_account, r)
            except EndpointConnectionError as e:
                # Great, Another region that was introduced without GuardDuty Support
                logger.warning(f"EndpointConnectionError for SageMaker in region {r}")
            except ClientError as e:
                if e.response['Error']['Code'] == 'AccessDeniedException':
                    logger.warning(f"Access Denied for SageMaker in region {r} for account {target_account.account_name}({target_account.account_id}): {e}")
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


def discover_notebooks(account, region):
    '''Discover all Database Instances (RDS)'''

    notebooks = []

    client = account.get_client('sagemaker', region=region)
    response = client.list_notebook_instances()
    while 'NextToken' in response:  # Gotta Catch 'em all!
        notebooks += response['NotebookInstances']
        response = client.list_notebook_instances(NextToken=response['NextToken'])
    notebooks += response['NotebookInstances']

    for nb in notebooks:
        name = nb['NotebookInstanceName']

        details = client.describe_notebook_instance(NotebookInstanceName=name)

        resource_item = {}
        resource_item['awsAccountId']                   = account.account_id
        resource_item['awsAccountName']                 = account.account_name
        resource_item['resourceType']                   = NOTEBOOK_TYPE
        resource_item['source']                         = "Antiope"
        resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
        resource_item['awsRegion']                      = region
        resource_item['configuration']                  = details
        resource_item['supplementaryConfiguration']     = {}
        resource_item['resourceName']                   = details['NotebookInstanceName']
        resource_item['resourceId']                     = f"{account.account_id}-{region}-{details['NotebookInstanceName']}"
        resource_item['ARN']                            = details['NotebookInstanceArn']
        resource_item['resourceCreationTime']           = details['CreationTime']
        resource_item['errors']                         = {}

        try:
            tags = client.list_tags(ResourceArn=details['NotebookInstanceArn'])
            resource_item['tags'] = parse_tags(tags['Tags'])
        except (ClientError, KeyError, IndexError):
            pass  # If Tags aren't present or whatever, just ignore

        save_resource_to_s3(NOTBOOK_RESOURCE_PATH, resource_item['resourceId'], resource_item)

