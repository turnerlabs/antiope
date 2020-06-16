import boto3
from botocore.exceptions import ClientError
import json
import os
import time
import datetime

from antiope.aws_account import *
from common import *

import logging
logger = logging.getLogger()
logger.setLevel(getattr(logging, os.getenv('LOG_LEVEL', default='INFO')))
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)


# Lambda main routine
def handler(event, context):
    logger.info("Received event: " + json.dumps(event, sort_keys=True))

    dynamodb = boto3.resource('dynamodb')
    account_table = dynamodb.Table(os.environ['ACCOUNT_TABLE'])

    client = boto3.client('sns')

    account_list = []  # The list of accounts that will be processed by this StepFunction execution
    new_event = event['Payload']['AWS-Inventory']

    for payer_id in new_event['payer']:
        payer_creds = get_account_creds(payer_id)
        if payer_creds is False:
            logger.error("Unable to assume role in payer {}".format(payer_id))
            continue

        logger.info("Processing payer {}".format(payer_id))
        payer_account_list = get_consolidated_billing_subaccounts(payer_creds)
        for a in payer_account_list:
            if 'Payer Id' not in a:
                a['Payer Id'] = payer_id

            # Update the stuff from AWS Organizations
            create_or_update_account(a, account_table)

            # Now test the cross-account role if the account is active
            if a[u'Status'] == "ACTIVE":
                my_account = AWSAccount(a['Id'])
                try:
                    creds = my_account.get_creds(session_name="test-audit-access")
                    # If an exception isn't thrown, this account is good.
                    # Add it to the list to process, and update the account's attribute
                    account_list.append(a['Id'])
                    my_account.update_attribute('cross_account_role', my_account.cross_account_role_arn)
                except AntiopeAssumeRoleError as e:
                    # Otherwise we log the error
                    logger.error("Unable to assume role into {}({})".format(a['Name'], a['Id']))
                    pass

        # Trigger the Payer-Level Functions
        message = new_event.copy()
        message['payer_id'] = payer_id  # Which account to process
        response = client.publish(
            TopicArn=os.environ['TRIGGER_PAYER_INVENTORY_ARN'],
            Message=json.dumps(message)
        )

    new_event['account_list'] = account_list

    # We'll use this for reports where we want every file to have the same timestamp suffix.
    new_event['timestamp'] = datetime.datetime.utcnow().strftime("%Y-%m-%d-%H-%M")
    return(new_event)

# end handler()

##############################################


def get_account_creds(account_id):
    role_arn = "arn:aws:iam::{}:role/{}".format(account_id, os.environ['ROLE_NAME'])
    client = boto3.client('sts')
    try:
        session = client.assume_role(RoleArn=role_arn, RoleSessionName=os.environ['ROLE_SESSION_NAME'])
        return(session['Credentials'])
    except Exception as e:
        logger.error(u"Failed to assume role {} in payer account {}: {}".format(role_arn, account_id, e))
        return(False)
# end get_account_creds()


def test_account_creds(account_id):
    role_arn = "arn:aws:iam::{}:role/{}".format(account_id, os.environ['ROLE_NAME'])
    client = boto3.client('sts')
    try:
        session = client.assume_role(RoleArn=role_arn, RoleSessionName=os.environ['ROLE_SESSION_NAME'])
        return(role_arn)
    except Exception as e:
        logger.error(u"Failed to assume role {} in payer account {}: {}".format(role_arn, account_id, e))
        return(False)
# end test_account_creds()


def get_consolidated_billing_subaccounts(session_creds):
    # Returns: [
    #         {
    #             'Id': 'string',
    #             'Arn': 'string',
    #             'Email': 'string',
    #             'Name': 'string',
    #             'Status': 'ACTIVE'|'SUSPENDED',
    #             'JoinedMethod': 'INVITED'|'CREATED',
    #             'JoinedTimestamp': datetime(2015, 1, 1)
    #         },
    #     ],
    org_client = boto3.client('organizations',
        aws_access_key_id = session_creds['AccessKeyId'],
        aws_secret_access_key = session_creds['SecretAccessKey'],
        aws_session_token = session_creds['SessionToken']
    )
    try:

        output = []
        response = org_client.list_accounts(MaxResults=20)
        while 'NextToken' in response:
            output = output + response['Accounts']
            time.sleep(1)
            response = org_client.list_accounts(MaxResults=20, NextToken=response['NextToken'])

        output = output + response['Accounts']
        return(output)
    except ClientError as e:
        if e.response['Error']['Code'] == 'AWSOrganizationsNotInUseException':
            # This is a standalone account
            sts_client = boto3.client('sts',
                aws_access_key_id = session_creds['AccessKeyId'],
                aws_secret_access_key = session_creds['SecretAccessKey'],
                aws_session_token = session_creds['SessionToken']
            )
            response = sts_client.get_caller_identity()
            account = {
                'Id': response['Account'],
                'Name': response['Account'],
                'Status': "ACTIVE",  # Assume it is active since we could assumerole to it.
                'Email': "StandAloneAccount"
            }
            logger.debug(f"Account info {account}")
            # If there is an IAM Alias, use that. There is no API to the account/billing portal we can
            # use to get an account name
            iam_client = boto3.client('iam',
                aws_access_key_id = session_creds['AccessKeyId'],
                aws_secret_access_key = session_creds['SecretAccessKey'],
                aws_session_token = session_creds['SessionToken']
            )
            response = iam_client.list_account_aliases()
            if 'AccountAliases' in response and len(response['AccountAliases']) > 0:
                account['Name'] = response['AccountAliases'][0]

            return([account])

        # This is what we get if we're a child in an organization, but not inventorying the payer
        elif e.response['Error']['Code'] == 'AccessDeniedException':
            sts_client = boto3.client('sts',
                aws_access_key_id = session_creds['AccessKeyId'],
                aws_secret_access_key = session_creds['SecretAccessKey'],
                aws_session_token = session_creds['SessionToken']
            )
            response = sts_client.get_caller_identity()
            account_id = response['Account']
            account = {
                'Id': account_id,
                'Name': account_id,
                'Status': "ACTIVE",  # Assume it is active since we could assumerole to it.
                'Email': "Unknown"
            }

            # We can get a few details from this....
            response = org_client.describe_organization()
            account['Payer Id'] = response['Organization']['MasterAccountId']
            account['Arn'] = f"{response['Organization']['Arn']}/{account_id}"

            # If there is an IAM Alias, use that for Name. There is no API to the account/billing portal we can
            # use to get an account name
            iam_client = boto3.client('iam',
                aws_access_key_id = session_creds['AccessKeyId'],
                aws_secret_access_key = session_creds['SecretAccessKey'],
                aws_session_token = session_creds['SessionToken']
            )
            response = iam_client.list_account_aliases()
            if 'AccountAliases' in response and len(response['AccountAliases']) > 0:
                account['Name'] = response['AccountAliases'][0]

            return([account])
        else:
            raise


# end get_consolidated_billing_subaccounts()


def create_or_update_account(a, account_table):
    logger.info(u"Adding account {} with name {} and email {}".format(a[u'Id'], a[u'Name'], a[u'Email']))
    if 'JoinedTimestamp' in a:
        a[u'JoinedTimestamp'] = a[u'JoinedTimestamp'].isoformat()  # Gotta convert to make the json save
    try:
        response = account_table.update_item(
            Key= {'account_id': a[u'Id']},
            UpdateExpression="set account_name=:name, account_status=:status, payer_id=:payer_id, root_email=:root_email, payer_record=:payer_record",
            ExpressionAttributeValues={
                ':name':        a[u'Name'],
                ':status':      a[u'Status'],
                ':payer_id':    a[u'Payer Id'],
                ':root_email':  a[u'Email'],
                ':payer_record': a
            }
        )

    except ClientError as e:
        raise AccountUpdateError(u"Unable to create {}: {}".format(a[u'Name'], e))
