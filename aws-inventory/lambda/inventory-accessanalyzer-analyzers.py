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

RESOURCE_PATH = "accessanalyzer/analyzer"
RESOURCE_TYPE = "AWS::AccessAnalyzer::Analyzer"

FINDING_PATH = "accessanalyzer/finding"
FINDING_TYPE = "AWS::AccessAnalyzer::Finding"

def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:

        # This function is to be attached to both a
        if 'payer_id' in message:
            payer_account = AWSAccount(message['payer_id'])
            target_account = payer_account.get_delegated_admin_account_for_service('access-analyzer')
            account_id = message['payer_id']
            org_level = True
        elif 'account_id' in message:
            account_id = message['account_id']
            target_account = AWSAccount(message['account_id'])
            org_level = False
        else:
            raise("Message contained neither account_id nor payer_id")

        regions = target_account.get_regions()
        if 'region' in message:
            regions = [message['region']]

        # describe ec2 instances
        for r in regions:
            client = target_account.get_client('accessanalyzer', region=r)
            analyzer = get_analyzer(target_account, client, r)
            if analyzer is None:
                logger.error(f"No Analyzers configured for {target_account.account_name}({target_account.account_id}) in {r}")
                continue
            get_findings(target_account, client, r, analyzer)

    except AntiopeAssumeRoleError as e:
        logger.error("Unable to assume role into account {}({})".format(target_account.account_name, target_account.account_id))
        return()
    except AntiopeAssumeRoleError as e:
        logger.error("Unable to assume role into account {}({})".format(target_account.account_name, target_account.account_id))
        return()
    except ClientError as e:
        if e.response['Error']['Code'] == 'AccessDeniedException':
            logger.error(f"AccessDeniedException for access-analyzer in {target_account.account_name}({target_account.account_id})")
            return()
        else:
            logger.critical("AWS Error getting info for {}: {}".format(account_id, e))
            capture_error(message, context, e, "ClientError for {}: {}".format(account_id, e))
            raise
    except Exception as e:
        logger.critical("{}\nMessage: {}\nContext: {}".format(e, message, vars(context)))
        capture_error(message, context, e, "General Exception for {}: {}".format(account_id, e))
        raise


def get_analyzer(target_account, client, region):
    analyzers = []
    response = client.list_analyzers()
    while 'nextToken' in response:
        analyzers += response['analyzers']
        response = client.list_analyzers(nextToken=response['nextToken'])
    analyzers += response['analyzers']

    # There may be no analyzers in this region, so we return none
    if len(analyzers) == 0:
        return(None)

    for a in analyzers:
        resource_item = {}
        resource_item['awsAccountId']                   = target_account.account_id
        resource_item['awsAccountName']                 = target_account.account_name
        resource_item['resourceType']                   = RESOURCE_TYPE
        resource_item['source']                         = "Antiope"
        resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
        resource_item['awsRegion']                      = region
        resource_item['configuration']                  = a
        resource_item['supplementaryConfiguration']     = {}
        resource_item['resourceId']                     = f"{target_account.account_id}-{region}-{a['name']}"
        resource_item['ARN']                            = a['arn']
        resource_item['errors']                         = {}
        save_resource_to_s3(RESOURCE_PATH, resource_item['resourceId'], resource_item)

    # There can currently only be one analyzer. When that changes this part needs to be fixed
    return(analyzers[0]['arn'])  # Arn is needed for getting findings


def get_findings(target_account, client, region, analyzer_arn):

    findings = get_all_findings(client, analyzer_arn, region)
    logger.info(f"Found {len(findings)} findings for {analyzer_arn} in {region}")

    # dump info about instances to S3 as json
    for f in findings:

        resource_item = {}
        resource_item['awsAccountId']                   = target_account.account_id
        resource_item['awsAccountName']                 = target_account.account_name
        resource_item['resourceType']                   = FINDING_TYPE
        resource_item['source']                         = "Antiope"
        resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
        resource_item['awsRegion']                      = region
        resource_item['configuration']                  = f
        resource_item['supplementaryConfiguration']     = {}
        resource_item['resourceId']                     = f['id']
        resource_item['resourceCreationTime']           = f['createdAt']
        resource_item['errors']                         = {}
        save_resource_to_s3(FINDING_PATH, resource_item['resourceId'], resource_item)

def get_delegated_admin(payer_account):


def get_all_findings(client, arn, region):
    output = []
    response = client.list_findings(analyzerArn=arn, maxResults=100)
    while 'nextToken' in response:
        for f in response['findings']:
            # Only save IAM Findings in us-east-1
            if f['resourceType'] == "AWS::IAM::Role" and region != "us-east-1":
                continue
            output.append(f)
        response = client.list_findings(analyzerArn=arn, maxResults=100, nextToken=response['nextToken'])
    for f in response['findings']:
        # Only save IAM Findings in us-east-1
        if f['resourceType'] == "AWS::IAM::Role" and region != "us-east-1":
            continue
        output.append(f)
    return(output)
