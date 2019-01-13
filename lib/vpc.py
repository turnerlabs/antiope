import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import json
import os
import logging
import datetime
from dateutil import tz
from pprint import pprint

from lib.account import *

class VPC(object):
    """Class to represent a VPC belonging to an Account"""
    def __init__(self, vpc_id, account=None):
        '''create a new VPC Instance from the vpc_id from data in the VPC Table'''
        super(VPC, self).__init__()
        self.vpc_id = vpc_id

        self.dynamodb      = boto3.resource('dynamodb')
        self.account_table = self.dynamodb.Table(os.environ['ACCOUNT_TABLE'])
        self.vpc_table     = self.dynamodb.Table(os.environ['VPC_TABLE'])

        # Get the VPC data from the VPC DDB Table. Raise the VPCLookupError if not present
        try:
            response = self.vpc_table.query(
                KeyConditionExpression=Key('vpc_id').eq(self.vpc_id),
                Select='ALL_ATTRIBUTES'
            )
        except ClientError as e:
            raise VPCLookupError("ClientError getting {}: {}".format(self.vpc_id, e))

        try:
            self.db_record = response['Items'][0]

            # Make sure there is a name, if not then use the VPC ID
            if 'name' not in self.db_record:
                self.db_record['name'] = self.vpc_id

            # Convert the response into instance attributes
            self.__dict__.update(self.db_record)
        except IndexError as e:
            raise VPCLookupError("ID {} not found".format(vpc_id))
        except Exception as e:
            logger.error("Got Other error: {}".format(e))

        # We should reference our account in the VPC object. Perhaps the object exists and is part of the init(),
        # perhaps it isn't and we need to create a new one.
        if account == None:
            # This will fail because AWSAccount is not defined and can't be imported due to circular dependencies
            # (AWSAccount requires VPC too)
            self.account = AWSAccount(self.account_id)
        else:
            self.account = account

    def __str__(self):
        """when converted to a string, become the account_id"""
        return(self.vpc_id)

    def __repr__(self):
        '''Create a useful string for this class if referenced'''
        return("<VPC {} >".format(self.vpc_id))



    #
    # Database functions
    #
    def update_vpc_attribute(self, key, value):
        '''    update a specific attribute in a specific table for this account
            table_name should be a valid DynDB table, key is the column, value is the new value to set
        '''
        logger.info(u"Adding key:{} value:{} to VPC {}".format(key, value, self))
        try:
            response = self.vpc_table.update_item(
                Key= {
                    'vpc_id': self.vpc_id
                },
                UpdateExpression="set {} = :r".format(key),
                ExpressionAttributeValues={
                ':r': value,
                }
            )
            setattr(self, key, value) # Also update this instance of the object
        except ClientError as e:
            raise VPCUpdateError("Failed to update {} to {} for {}: {}".format(key, value, self, e))

    def get_vpc_attribute(self, key):
        '''
        Pulls a attribute from the specificed table for the account
        '''
        logger.info(u"Getting key: {} for {}".format(key, self))
        try:
            response = self.vpc_table.get_item(
                Key= {
                    'vpc_id': self.vpc_id
                },
                AttributesToGet=[ key ]
            )
            return(response['Item'][key])
        except ClientError as e:
            raise VPCLookupError("Failed to get {} for {}: {}".format(key, self, e))
        except KeyError as e:
            raise VPCLookupError("Failed to get {} for {}: {}".format(key, self, e))


    #
    # Instance Attributes
    #

    def query_instances(self, instance_state = None):
        '''return an array of dict representing the data from describe_instances()'''
        output = []

        filters = [ { 'Name': 'vpc-id', 'Values': [ self.vpc_id ] } ]
        if instance_state is not None:
            filters.append({'Name': 'instance-state-name', 'Values': [ instance_state ]})

        try:
            # Get a boto3 EC2 Resource in this VPC's region.
            ec2 = self.account.get_client('ec2', self.region)
            response = ec2.describe_instances(
                Filters = filters,
                MaxResults = 1000
            )
            while 'NextToken' in response:
                for r in response['Reservations']:
                    for i in r['Instances']:
                        output.append(i)
                response = ec2.describe_instances(
                    Filters = filters,
                    MaxResults = 1000,
                    NextToken = response['NextToken']
                )
            # Done with the while loop (or never entered it) do the last batch
            for r in response['Reservations']:
                for i in r['Instances']:
                    output.append(i)
            return(output)
        except ClientError as e:
            raise VPCLookupError("Failed to query_instances() for {}: {}".format(self, e))

    def query_running_instances(self):
        '''return an array of dict representing the data from describe_instances(). Only includes running instances'''
        return(self.query_instances(instance_state = "running"))

    def discover_instance_count(self):
        '''Get the number of instances in the VPC, update the count in the database'''

        # FIXME (someday) - if the last_updated is within some timeperiod, then don't make the API calls, just used the cached info

        state_count = {
            "pending": 0,
            "running": 0,
            "shutting-down": 0,
            "terminated": 0,
            "stopping": 0,
            "stopped": 0
        }

        instances = self.query_instances()
        for i in instances:
            state = i['State']['Name']
            state_count[state] += 1

        item = {
            "last_updated": str(datetime.datetime.now(tz.gettz('US/Eastern'))),
            "states": state_count
        }

        self.update_vpc_attribute("instance_states", item)
        return(state_count)

    def is_active(self):
        '''Returns true if there are active EC2 Instances running in this VPC'''

        if not hasattr(self, "instance_states"):
            self.discover_instance_count()

        if self.instance_states['running'] > 0:  # FIXME, do something about the instance counts being stale
            return(True)
        return(False)


class VPCLookupError(LookupError):
    '''Raised when the VPC requested is not in the database'''

class VPCUpdateError(LookupError):
    '''Raised when the VPC requested is not in the database'''