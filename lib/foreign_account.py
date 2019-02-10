
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import json
import os
import logging
import datetime
from dateutil import tz
from pprint import pprint

from lib.vpc import *

import logging
logger = logging.getLogger()

class ForeignAWSAccount(object):
    """Class to represent an AWS Account """
    def __init__(self, account_id):
        """ Create a new object representing the AWS account specified by account_id """
        # Execute any parent class init()
        super(ForeignAWSAccount, self).__init__()

        self.account_id = account_id

        # # Save these as attributes
        self.dynamodb      = boto3.resource('dynamodb')
        self.account_table = self.dynamodb.Table(os.environ['ACCOUNT_TABLE'])

        response = self.account_table.query(
            KeyConditionExpression=Key('account_id').eq(self.account_id),
            Select='ALL_ATTRIBUTES'
        )
        try:
            self.db_record = response['Items'][0]
            # Convert the response into instance attributes
            self.__dict__.update(self.db_record)
            # self.account_name = str(self.account_name.encode('ascii', 'ignore'))
        except IndexError as e:
            raise AccountLookupError("ID {} not found".format(account_id))
        except Exception as e:
            logger.error("Got Other error: {}".format(e))

    def __str__(self):
        """when converted to a string, become the account_id"""
        return(self.account_id)

    def __repr__(self):
        """Create a useful string for this class if referenced"""
        return("<ForeignAWSAccount {} >".format(self.account_id))


    #
    # Database functions
    #
    def update_attribute(self, key, value):
        """
        Update a specific attribute in a specific table for this account.
        key is the column, value is the new value to set
        """
        logger.info(u"Adding key:{} value:{} to account {}".format(key, value, self))
        try:
            response = self.account_table.update_item(
                Key= {
                    'account_id': self.account_id
                },
                UpdateExpression="set #k = :r",
                ExpressionAttributeNames={
                    '#k': key
                },
                ExpressionAttributeValues={
                ':r': value,
                }
            )
        except ClientError as e:
            raise AccountUpdateError("Failed to update {} to {} in account table: {}".format(key, value, e))

    def get_attribute(self, key):
        """
        Fetches a attribute from the specificed table for the account
        """
        logger.info(u"Getting key:{} from account_table for account {}".format(key, self))
        try:
            response = self.account_table.get_item(
                Key= {
                    'account_id': self.account_id
                },
                AttributesToGet=[ key ]
            )
            return(response['Item'][key])
        except ClientError as e:
            raise AccountLookupError("Failed to get {} from {} in account table: {}".format(key, self, e))
        except KeyError as e:
            raise AccountLookupError("Failed to get {} from {} in account table: {}".format(key, self, e))

    def delete_attribute(self, key):
        """
        Delete a attribute from the specificed table for the account
        """
        logger.info(u"Deleting key:{} from account table for account {}".format(key, self))
        table = self.account_table
        try:
            response = table.update_item(
                Key= {
                    'account_id': self.account_id
                },
                UpdateExpression="remove #k",
                ExpressionAttributeNames={
                    '#k': key
                },
                # ExpressionAttributeValues={
                # ':r': value,
                # }
            )
        except ClientError as e:
            raise AccountLookupError("Failed to get {} from {} in account table: {}".format(key, self, e))
        except KeyError as e:
            raise AccountLookupError("Failed to get {} from {} in account table: {}".format(key, self, e))


class AssumeRoleError(Exception):
    """raised when the AssumeRole Fails"""

class AccountUpdateError(Exception):
    """raised when an update to DynamoDB Fails"""

class AccountLookupError(LookupError):
    """Raised when the Account requested is not in the database"""
