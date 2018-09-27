import boto3
from botocore.exceptions import ClientError

import json
import os
import time

import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)


# Lambda main routine
def handler(event, context):
    logger.info("Received event: " + json.dumps(event, sort_keys=True))

    dynamodb = boto3.resource('dynamodb')
    account_table = dynamodb.Table(os.environ['ACCOUNT_TABLE'])

    account_list = []

    for payer_id in event['payer']:
        payer_creds = get_account_creds(payer_id)
        if payer_creds == False:
            logger.error("Unable to assume role in payer {}".format(payer_id))
            continue

        logger.info("Processing payer {}".format(payer_id))
        payer_account_list = get_consolidated_billing_subaccounts(payer_creds)
        for a in payer_account_list:
            a['Payer Id'] = payer_id

            create_or_update_account(a, account_table)

            if get_account_creds(a['Id']):
                # Now trigger the parallel collection of data
                client = boto3.client('sns')
                message = {}
                message['account_id'] = a['Id']
                response = client.publish(
                    TopicArn=os.environ['TRIGGER_ACCOUNT_INVENTORY_ARN'],
                    Message=json.dumps(message)
                )
            else:
                logger.error("Unable to assume role into {}({})".format(a['Name'], a['Id']))
            account_list.append(a['Id'])

    event['account_list'] = account_list
    return(event)

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
    try:
        org_client = boto3.client('organizations',
            aws_access_key_id = session_creds['AccessKeyId'],
            aws_secret_access_key = session_creds['SecretAccessKey'],
            aws_session_token = session_creds['SessionToken']
            )
        output = []
        response = org_client.list_accounts( MaxResults=20 )
        while 'NextToken' in response :
            output = output + response['Accounts']
            time.sleep(1)
            response = org_client.list_accounts( MaxResults=20,
                NextToken=response['NextToken'] )

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
                'Status': "ACTIVE", # Assume it is active since we could assumerole to it.
                'Email': "StandAloneAccount"
                }

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
        else:
            raise ClientError(e)


# end get_consolidated_billing_subaccounts()


def create_or_update_account(a, account_table):
    logger.info(u"Adding account {} with name {} and email {}".format(a[u'Id'], a[u'Name'], a[u'Email']))
    if 'JoinedTimestamp' in a:
        a[u'JoinedTimestamp'] = a[u'JoinedTimestamp'].isoformat() # Gotta convert to mmake the json save
    try:
        response = account_table.put_item(
            Item={
                'account_id'     : a[u'Id'],
                'account_name'   : a[u'Name'],
                'account_status' : a[u'Status'],
                'payer_id'       : a[u'Payer Id'],
                'root_email'     : a[u'Email'],
                'payer_record'   : a
            }
        )
    except ClientError as e:
        raise AccountUpdateError(u"Unable to create {}: {}".format(a[u'Name'], e))

