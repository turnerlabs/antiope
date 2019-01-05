
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import json
import os
import logging
import datetime
from dateutil import tz
from pprint import pprint



class GCPProject(object):
    """Class to represent a GCP Project """
    def __init__(self, projectId):
        '''
            Takes an projectId as the lookup attribute
        '''
        # Execute any parent class init()
        super(GCPProject, self).__init__()

        self.projectId = projectId

        # # Save these as attributes
        self.dynamodb      = boto3.resource('dynamodb')
        self.project_table = self.dynamodb.Table(os.environ['PROJECT_TABLE'])

        response = self.project_table.query(
            KeyConditionExpression=Key('projectId').eq(self.projectId),
            Select='ALL_ATTRIBUTES'
        )
        try:
            item = response['Items'][0]
            # Convert the response into instance attributes
            self.__dict__.update(item)
        except IndexError as e:
            raise ProjectLookupError("ID {} not found".format(projectId))
        except Exception as e:
            logger.error("Got Other error: {}".format(e))

    def __str__(self):
        """when converted to a string, become the projectId"""
        return(self.projectId)

    def __repr__(self):
        '''Create a useful string for this class if referenced'''
        return("<Antiope.GCPProject {} >".format(self.projectId))


    #
    # Database functions
    #

    def update_attribute(self, table_name, key, value):
        '''    update a specific attribute in a specific table for this project
            table_name should be a valid DynDB table, key is the column, value is the new value to set
        '''
        logger.info(u"Adding key:{} value:{} to project {}".format(key, value, self))
        table = self.dynamodb.Table(table_name)
        try:
            response = table.update_item(
                Key= {
                    'projectId': self.projectId
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
            raise ProjectUpdateError("Failed to update {} to {} in {}: {}".format(key, value, table_name, e))

    def get_attribute(self, table_name, key):
        '''
        Pulls a attribute from the specificed table for the project
        '''
        logger.info(u"Getting key:{} from:{} for project {}".format(key, table_name, self))
        table = self.dynamodb.Table(table_name)
        try:
            response = table.get_item(
                Key= {
                    'projectId': self.projectId
                },
                AttributesToGet=[ key ]
            )
            return(response['Item'][key])
        except ClientError as e:
            raise ProjectLookupError("Failed to get {} from {} in {}: {}".format(key, table_name, self, e))
        except KeyError as e:
            raise ProjectLookupError("Failed to get {} from {} in {}: {}".format(key, table_name, self, e))

    def delete_attribute(self, table_name, key):
        '''
        Pulls a attribute from the specificed table for the project
        '''
        logger.info(u"Deleting key:{} from:{} for project {}".format(key, table_name, self))
        table = self.dynamodb.Table(table_name)
        try:
            response = table.update_item(
                Key= {
                    'projectId': self.projectId
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
            raise ProjectLookupError("Failed to get {} from {} in {}: {}".format(key, table_name, self, e))
        except KeyError as e:
            raise ProjectLookupError("Failed to get {} from {} in {}: {}".format(key, table_name, self, e))


class AssumeRoleError(Exception):
    '''raised when the AssumeRole Fails'''

class ProjectUpdateError(Exception):
    '''raised when an update to DynamoDB Fails'''

class ProjectLookupError(LookupError):
    '''Raised when the Project requested is not in the database'''
