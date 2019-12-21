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

RESOURCE_PATH = "accessanalyzer/analyzer"
RESOURCE_TYPE = "AWS::AccessAnalyzer::Analyzer"

FINDING_PATH = "accessanalyzer/finding"
FINDING_TYPE = "AWS::AccessAnalyzer::Finding"

def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])

        regions = target_account.get_regions()
        if 'region' in message:
            regions = [message['region']]

        # describe ec2 instances
        for r in regions:
            client = target_account.get_client('accessanalyzer', region=r)
            analyzer = get_analyzer(target_account, client, r)
            if analyzer is None:
                logger.error(f"No Analyzers configured for {target_account.account_name}({target_account.account_id}) in {region}")
                return(event)
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
            logger.critical("AWS Error getting info for {}: {}".format(message['account_id'], e))
            capture_error(message, context, e, "ClientError for {}: {}".format(message['account_id'], e))
            raise
    except Exception as e:
        logger.critical("{}\nMessage: {}\nContext: {}".format(e, message, vars(context)))
        capture_error(message, context, e, "General Exception for {}: {}".format(message['account_id'], e))
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

    findings = get_all_findings(client, analyzer_arn)
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


def get_all_findings(client, arn):
    output = []
    response = client.list_findings(analyzerArn=arn)
    while 'nextToken' in response:
        output += response['findings']
        response = client.list_findings(analyzerArn=arn, nextToken=response['nextToken'])
    output += response['findings']
    return(output)
