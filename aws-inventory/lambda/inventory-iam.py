

import boto3
from botocore.exceptions import ClientError
import json
import os
import time
from datetime import datetime, timezone
from dateutil import tz
import re
from xml.dom.minidom import parseString

from antiope.aws_account import *
from common import *

import logging
logger = logging.getLogger()
logger.setLevel(getattr(logging, os.getenv('LOG_LEVEL', default='INFO')))
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

USER_RESOURCE_PATH = "iam/user"
ROLE_RESOURCE_PATH = "iam/role"
SAML_RESOURCE_PATH = "iam/saml"


def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        discover_roles(target_account)
        discover_users(target_account)
        discover_saml_provider(target_account)
        fetch_credential_report(target_account, message)

    except AntiopeAssumeRoleError as e:
        logger.error("Unable to assume role into account {}({})".format(target_account.account_name, target_account.account_id))
        return()
    except ClientError as e:
        logger.critical("AWS Error getting info for {}: {}".format(message['account_id'], e))
        capture_error(message, context, e, "ClientError for {}: {}".format(message['account_id'], e))
        raise
    except Exception as e:
        logger.critical("{}\nMessage: {}\nContext: {}".format(e, message, vars(context)))
        capture_error(message, context, e, "General Exception for {}: {}".format(message['account_id'], e))
        raise


def discover_roles(account):
    '''
        Discovers all IAM Roles. If there is a trust relationship to an external account it will note that.
    '''
    roles = []

    iam_client = account.get_client('iam')
    response = iam_client.list_roles()
    while 'IsTruncated' in response and response['IsTruncated'] is True:  # Gotta Catch 'em all!
        roles += response['Roles']
        response = iam_client.list_roles(Marker=response['Marker'])  # I love how the AWS API is so inconsistent with how they do pagination.
    roles += response['Roles']

    for role in roles:
        try:
            process_role(role, account, iam_client)
        except ClientError as e:
            if e.response['Error']['Code'] == "Throttling":
                logger.error(f"Hit a Throttling Exception {e}")
                time.sleep(1)
                process_role(role, account, iam_client)
            else:
                raise


def process_role(role, account, iam_client):

    resource_item = {}
    resource_item['awsAccountId']                   = account.account_id
    resource_item['awsAccountName']                 = account.account_name
    resource_item['resourceType']                   = "AWS::IAM::Role"
    resource_item['source']                         = "Antiope"
    resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
    resource_item['configuration']                  = role
    if 'Tags' in role:
        resource_item['tags']                           = parse_tags(role['Tags'])
    resource_item['supplementaryConfiguration']     = {}
    resource_item['resourceId']                     = role['RoleId']
    resource_item['resourceName']                   = role['RoleName']
    resource_item['ARN']                            = role['Arn']
    resource_item['resourceCreationTime']           = role['CreateDate']
    resource_item['errors']                         = {}

    # Fetch the policies attached to this role
    response = iam_client.list_role_policies(RoleName=role['RoleName']) # FIXME Paganation can occur.
    resource_item['supplementaryConfiguration']['PolicyNames'] = response['PolicyNames']

    response = iam_client.list_attached_role_policies(RoleName=role['RoleName']) # FIXME Paganation can occur.
    resource_item['supplementaryConfiguration']['AttachedPolicies'] = response['AttachedPolicies']

    save_resource_to_s3(ROLE_RESOURCE_PATH, resource_item['resourceId'], resource_item)

    # Now here is the interesting bit. What other accounts does this role trust, and do we know them?
    for s in role['AssumeRolePolicyDocument']['Statement']:
        if s['Principal'] == "*":  # Dear mother of god, you're p0wned
            logger.error("Found an assume role policy that trusts everything!!!: {}".format(role_arn))
            # raise GameOverManGameOverException("Found an assume role policy that trusts everything!!!: {}".format(role['Arn']))
            # Put this into the resource under a specific key so we can search on these later
            response['CriticalFinding'] == f"Found an assume role policy that trusts everything!!!: {role['Arn']}"
        elif 'AWS' in s['Principal']:  # This means it's trusting an AWS Account and not an AWS Service.
            if type(s['Principal']['AWS']) is list:
                for p in s['Principal']['AWS']:
                    process_trusted_account(p, role['Arn'])
            else:
                process_trusted_account(s['Principal']['AWS'], role['Arn'])


def process_trusted_account(principal, role_arn):
    '''Given an AWS Principal, determine if the account is known, and if not known, add to the accounts database'''
    dynamodb = boto3.resource('dynamodb')
    account_table = dynamodb.Table(os.environ['ACCOUNT_TABLE'])

    # Principals can be an ARN, or just an account ID.
    if principal.startswith("arn"):
        account_id = principal.split(':')[4]
    elif re.match('^[0-9]{12}$', principal):
        account_id = principal
    elif principal == "*":
        logger.error("Found an assume role policy that trusts everything!!!: {}".format(role_arn))
        return()  # No accounts to add to the DB
    else:
        logger.error("Unable to identify what kind of AWS Principal this is: {}".format(principal))
        return()

    response = account_table.get_item(
        Key={'account_id': account_id},
        AttributesToGet=['account_id', 'account_status'],
        ConsistentRead=True
    )
    if 'Item' not in response:
        logger.info(u"Adding foreign account {}".format(account_id))
        try:
            response = account_table.put_item(
                Item={
                    'account_id':       account_id,
                    'account_name':     "unknown",
                    'account_status':   "FOREIGN",
                }
            )
        except ClientError as e:
            raise AccountUpdateError(u"Unable to create {}: {}".format(a[u'Name'], e))


def discover_users(account):
    '''
        Queries AWS to determine IAM Users exist in an AWS Account
    '''
    users = []

    iam_client = account.get_client('iam')
    response = iam_client.list_users()
    while 'IsTruncated' in response and response['IsTruncated'] is True:  # Gotta Catch 'em all!
        users += response['Users']
        response = iam_client.list_users(Marker=response['Marker'])
    users += response['Users']

    resource_item = {}
    resource_item['awsAccountId']                   = account.account_id
    resource_item['awsAccountName']                 = account.account_name
    resource_item['resourceType']                   = "AWS::IAM::User"
    resource_item['source']                         = "Antiope"

    for user in users:
        resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
        resource_item['configuration']                  = user
        if 'Tags' in user:
            resource_item['tags']                           = parse_tags(user['Tags'])
        resource_item['supplementaryConfiguration']     = {}
        resource_item['resourceId']                     = user['UserId']
        resource_item['resourceName']                   = user['UserName']
        resource_item['ARN']                            = user['Arn']
        resource_item['resourceCreationTime']           = user['CreateDate']
        resource_item['errors']                         = {}

        response = iam_client.list_mfa_devices(UserName=user['UserName'])
        if 'MFADevices' in response and len(response['MFADevices']) > 0:
            resource_item['supplementaryConfiguration']['MFADevice'] = response['MFADevices'][0]

        response = iam_client.list_access_keys(UserName=user['UserName'])
        if 'AccessKeyMetadata' in response and len(response['AccessKeyMetadata']) > 0:
            resource_item['supplementaryConfiguration']['AccessKeyMetadata'] = response['AccessKeyMetadata']

        try:
            response = iam_client.get_login_profile(UserName=user['UserName'])
            if 'LoginProfile' in response:
                resource_item['supplementaryConfiguration']['LoginProfile'] = response["LoginProfile"]
        except ClientError as e:
            if e.response['Error']['Code'] == "NoSuchEntity":
                pass
            else:
                raise

        save_resource_to_s3(USER_RESOURCE_PATH, resource_item['resourceId'], resource_item)


def discover_saml_provider(account):
    '''
        Queries AWS to determine SAML Providers exist (and who you're trusting)
    '''
    iam_client = account.get_client('iam')
    response = iam_client.list_saml_providers()

    resource_item = {}
    resource_item['awsAccountId']                   = account.account_id
    resource_item['awsAccountName']                 = account.account_name
    resource_item['resourceType']                   = "AWS::IAM::SAML"
    resource_item['source']                         = "Antiope"

    for idp in response['SAMLProviderList']:

        # The Metadata doc (with the useful deets) are in an XML doc that requires another call
        saml = iam_client.get_saml_provider(SAMLProviderArn=idp['Arn'])
        metadata_xml = parseString(saml['SAMLMetadataDocument'])
        idp['SAMLMetadataDocument'] = metadata_xml.toprettyxml()

        # We get the name from the end of the arn
        name = idp['Arn'].split("/")[-1]

        resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
        resource_item['configuration']                  = idp
        resource_item['supplementaryConfiguration']     = {}
        resource_item['resourceId']                     = f"{name}-{account.account_id}"
        resource_item['resourceName']                   = name
        resource_item['ARN']                            = idp['Arn']
        resource_item['resourceCreationTime']           = idp['CreateDate']
        resource_item['errors']                         = {}

        save_resource_to_s3(SAML_RESOURCE_PATH, resource_item['resourceId'], resource_item)


def fetch_credential_report(account, event):
    '''
        Fetches the IAM User Credential Report and saves it to S3
    '''
    iam_client = account.get_client('iam')
    csv_data = get_credential_report(iam_client)
    object_key = f"CredentialReports/{account.account_id}-{event['timestamp']}.csv"

    s3_client = boto3.client('s3')
    try:
        response = s3_client.put_object(
            # ACL='public-read',
            Body=csv_data,
            Bucket=os.environ['INVENTORY_BUCKET'],
            ContentType='text/csv',
            Key=object_key,
        )
    except ClientError as e:
        logger.error("ClientError saving report: {}".format(e))
        raise


def get_credential_report(iam_client):
    '''Fetches the credential report. Uses recursion in case the report isn't available immediatly'''

    # Lets see if a report is already available
    try:
        response = iam_client.get_credential_report()
        credential_report_csv = response['Content'].decode('ascii')
        return(credential_report_csv)
    except ClientError as e:
        if e.response['Error']['Code'] == "ReportNotPresent":
            pass
        elif e.response['Error']['Code'] == "ReportInProgress":
            time.sleep(2)
            return get_credential_report(iam_client)
        else:
            raise  # Whatever happened here we didn't expect

    try:
        # No report - go request one get generated
        resp1 = iam_client.generate_credential_report()
        if resp1['State'] == 'COMPLETE':
            try:
                response = iam_client.get_credential_report()
                credential_report_csv = response['Content'].decode('ascii')
                # # print(credential_report_csv)
                # reader = csv.DictReader(credential_report_csv.splitlines())
                # # print(reader)
                # # print(reader.fieldnames)
                # credential_report = []
                # for row in reader:
                #     credential_report.append(row)
                return(credential_report_csv)
            except ClientError as e:
                print("Unknown error getting Report: " + e.message)
        else:
            time.sleep(2)
            return get_credential_report(iam_client)
    except ClientError as e:
        if e.response['Error']['Code'] == "Throttling":
            time.sleep(2)
            return get_credential_report(iam_client)
        else:
            raise

