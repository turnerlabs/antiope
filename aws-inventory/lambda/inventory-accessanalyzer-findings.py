import boto3
from botocore.exceptions import ClientError
import json
import os
import time
from datetime import datetime, timezone
from dateutil import tz

from antiope.aws_account import *
from antiope.aws_organization import *
from common import *

import logging
logger = logging.getLogger()
logger.setLevel(getattr(logging, os.getenv('LOG_LEVEL', default='INFO')))
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)


def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:

        payer_account = AWSOrganizationMaster(message['payer_id'])
        delegated_account = payer_account.get_delegated_admin_account_for_service('access-analyzer')

        if delegated_account is None:
            logger.error(f"No AccessAnalyzer Delegation configured for payer {message['payer_id']}")
            return(event)

        account_id = message['payer_id']
        org_level = True

        if 'region' in message:
            regions = [message['region']]
        else:
            regions = delegated_account.get_regions()

        output = {}

        for r in regions:
            client = delegated_account.get_client('accessanalyzer', region=r)
            analyzer = get_analyzer(delegated_account, client, r)
            if analyzer is None:
                logger.error(f"No Analyzers configured for {delegated_account.account_name}({delegated_account.account_id}) in {r}")
                continue
            output[r] = get_findings(delegated_account, client, r, analyzer)

        save_findings(output, payer_account.org_id)

    except NotAnAWSOrganizationMaster:
        logger.error(f"{message['payer_id']} is not an Organization Master Account")
        return()
    except AntiopeAssumeRoleError as e:
        logger.error("Unable to assume role into account {}({})".format(delegated_account.account_name, delegated_account.account_id))
        return()
    except AntiopeAssumeRoleError as e:
        logger.error("Unable to assume role into account {}({})".format(delegated_account.account_name, delegated_account.account_id))
        return()
    except ClientError as e:
        if e.response['Error']['Code'] == 'AccessDeniedException':
            logger.error(f"AccessDeniedException for access-analyzer in {delegated_account.account_name}({delegated_account.account_id})")
            return()
        else:
            logger.critical("AWS Error getting info for {}: {}".format(message['payer_id'], e))
            capture_error(message, context, e, "ClientError for {}: {}".format(message['payer_id'], e))
            raise
    except Exception as e:
        logger.critical("{}\nMessage: {}\nContext: {}".format(e, message, vars(context)))
        capture_error(message, context, e, "General Exception for {}: {}".format(message['payer_id'], e))
        raise


def get_analyzer(delegated_account, client, region):
    response = client.list_analyzers(type='ORGANIZATION')
    analyzers = response['analyzers']

    # There may be no analyzers in this region, so we return none
    if len(analyzers) == 0:
        return(None)
    else:
        # There can currently only be one analyzer. When that changes this part needs to be fixed
        return(analyzers[0]['arn'])  # Arn is needed for getting findings


def get_findings(delegated_account, client, region, analyzer_arn):

    finding_filter={
        'isPublic': {'eq': ["true"] },
        'status': {'eq': ['ACTIVE'] }
    }

    # Exclude IAM resources unless in us-east-1
    if region != "us-east-1":
        finding_filter['resourceType'] = {'neq': ['AWS::IAM::Role']}

    findings = []
    response = client.list_findings(analyzerArn=analyzer_arn, maxResults=100, filter=finding_filter)
    while 'nextToken' in response:
        for f in response['findings']:
            findings.append(f)
        response = client.list_findings(analyzerArn=analyzer_arn, maxResults=100, filter=finding_filter, nextToken=response['nextToken'])
    for f in response['findings']:
        findings.append(f)

    logger.info(f"Found {len(findings)} findings for {analyzer_arn} in {region}")
    return(findings)


def save_findings(findings, orgId):
    # Save HTML and json to S3
    s3_client = boto3.client('s3')
    today = datetime.date.today()

    try:
        # Save the JSON to S3
        response = s3_client.put_object(
            Body=json.dumps(findings, sort_keys=True, indent=2, default=str),
            Bucket=os.environ['INVENTORY_BUCKET'],
            ContentType='application/json',
            Key=f"AccessAnalyzer/{orgId}-latest.json",
        )
        response = s3_client.put_object(
            Body=json.dumps(findings, sort_keys=True, indent=2, default=str),
            Bucket=os.environ['INVENTORY_BUCKET'],
            ContentType='application/json',
            Key=f"AccessAnalyzer/{orgId}-{today}.json",
        )
    except ClientError as e:
        logger.error("ClientError saving report: {}".format(e))
        raise
