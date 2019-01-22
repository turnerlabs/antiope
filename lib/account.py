
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

class AWSAccount(object):
    """Class to represent an AWS Account """
    def __init__(self, account_id):
        """ Create a new object representing the AWS account specified by account_id """
        # Execute any parent class init()
        super(AWSAccount, self).__init__()

        self.account_id = account_id

        # # Save these as attributes
        self.dynamodb      = boto3.resource('dynamodb')
        self.account_table = self.dynamodb.Table(os.environ['ACCOUNT_TABLE'])
        self.vpc_table     = self.dynamodb.Table(os.environ['VPC_TABLE'])

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

        self.cross_account_role_arn = "arn:aws:iam::{}:role/{}".format(self.account_id, os.environ['ROLE_NAME'])
        self.default_session_name = os.environ['ROLE_SESSION_NAME']

    def __str__(self):
        """when converted to a string, become the account_id"""
        return(self.account_id)

    def __repr__(self):
        """Create a useful string for this class if referenced"""
        return("<AWSAccount {} >".format(self.account_id))

    #
    # Cross Account Role Assumption Methods
    #
    def get_creds(self, session_name=None):
        """
        Request temporary credentials for the account. Returns a dict in the form of
        {
            creds['AccessKeyId'],
            creds['SecretAccessKey'],
            creds['SessionToken']
        }
        Which can be passed to a new boto3 client or resource.
        Takes an optional session_name which can be used by CloudTrail and IAM
        Raises AssumeRoleError() if the role is not found or cannot be assumed.
        """
        client = boto3.client('sts')

        if session_name is None:
            session_name = self.default_session_name

        try:
            session = client.assume_role(RoleArn=self.cross_account_role_arn, RoleSessionName=session_name)
            self.creds = session['Credentials'] # Save for later
            return(session['Credentials'])
        except ClientError as e:
            raise AssumeRoleError("Failed to assume role {} in account {} ({}): {}".format(self.cross_account_role_arn,
                self.account_name.encode('ascii', 'ignore'), self.account_id, e.response['Error']['Code']))

    def get_client(self, type, region=None, session_name=None):
        """
        Returns a boto3 client for the service "type" with credentials in the target account.
        Optionally you can specify the region for the client and the session_name for the AssumeRole.
        """
        if 'creds' not in self.__dict__:
            self.creds = self.get_creds(session_name=session_name)
        client = boto3.client(type,
            aws_access_key_id = self.creds['AccessKeyId'],
            aws_secret_access_key = self.creds['SecretAccessKey'],
            aws_session_token = self.creds['SessionToken'],
            region_name = region)
        return(client)

    def get_resource(self, type, region=None, session_name=None):
        """
        Returns a boto3 Resource for the service "type" with credentials in the target account.
        Optionally you can specify the region for the resource and the session_name for the AssumeRole.
        """
        if 'creds' not in self.__dict__:
            self.creds = self.get_creds(session_name=session_name)
        resource = boto3.resource(type,
            aws_access_key_id = self.creds['AccessKeyId'],
            aws_secret_access_key = self.creds['SecretAccessKey'],
            aws_session_token = self.creds['SessionToken'],
            region_name = region)
        return(resource)

    #
    # VPC Methods
    #
    def get_regions(self):
        """Return an array of the regions this account is active in. Ordered with us-east-1 in the front."""
        ec2 = self.get_client('ec2')
        response = ec2.describe_regions()
        output = ['us-east-1']
        for r in response['Regions']:
            if r['RegionName'] == "us-east-1":
                continue
            output.append(r['RegionName'])
        return(output)

    def get_vpc_ids(self):
        """Return a list of VPC ids for the account (as cached in the VPC Table)."""
        # TODO - Add support to filter by region
        output   = []
        vpc_list = []

        vpc_table = self.vpc_table
        response = vpc_table.query(
            IndexName='account-index',
            Select='SPECIFIC_ATTRIBUTES',
            ProjectionExpression='vpc_id',
            Limit=123,
            ConsistentRead=False,
            KeyConditionExpression=Key('account_id').eq(self.account_id)
        )
        while 'LastEvaluatedKey' in response :
            # Means that dynamoDB didn't return the full set, so as for more.
            vpc_list = vpc_list + response['Items']
            response = vpc_table.query(
                IndexName='account-index',
                Select='SPECIFIC_ATTRIBUTES',
                ProjectionExpression='vpc_id',
                Limit=123,
                ConsistentRead=False,
                KeyConditionExpression=Key('account_id').eq(self.account_id),
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
        vpc_list = vpc_list + response['Items']
        # Take the list of vpc_ids and instantiate VPC Objects. Return that list
        for v in vpc_list:
            output.append(v['vpc_id'])
        return(output)

    def get_vpcs(self, region=None):
        """Return a list of VPCs for the account (as cached in the VPC Table). Optionally filter it by region"""
        output   = []
        vpc_list = self.get_vpc_ids()
        for v in vpc_list:
            vpc = VPC(v,  account=self)
            if region is None:
                output.append(vpc)
            else:
                if vpc.region == region:
                    output.append(vpc)
        return(output)

    def get_active_vpcs(self, region=None):
        """Return a list of active VPCs (one or more running instances) for the account. Optionally filter it by region"""
        output   = []
        vpc_list = self.get_vpcs(region)

        # This could also work?
        # nonZeroVpcs =list(filter(lambda x: x.instance_count != '0', vpcs))
        for v in vpc_list:
            if v.is_active():
                output.append(v)
            # FIXME Filter out ones that haven't been updated in last 24 hrs
        return(output)

    #
    # Compliance Functions
    #

    def discover_cft_info_by_resource(self, PhysicalResourceId, region=None, VersionOutputKey='TemplateVersion'):
        """Jump into the account, and ask Cloudformation in that region about the details of a template"""
        output = {}

        try:
            if region == None:
                cfn_client      = self.get_client('cloudformation')
            else:
                cfn_client      = self.get_client('cloudformation', region=region)
        except AssumeRoleError:
            logger.error("Unable to assume role looking for {} in {}".format(PhysicalResourceId, self.account_id))
            return(None)

        # Ask Cloudformation "who owns PhysicalResourceId?"
        try:
            stack        = cfn_client.describe_stack_resources(PhysicalResourceId=PhysicalResourceId)
        except ClientError:
            # More error checking needed here.
            # logger.error("Failed to find CFT for {} in {}".format(PhysicalResourceId, self.account_id))
            return(None) # Nothing else to do. Go home and cry.

        for i in stack['StackResources']:
            if i['PhysicalResourceId'] == PhysicalResourceId:
                output['stack_name'] = i['StackName']
                output['Region'] = region
                break
        else:
            # How is it that describe_stack_resources() returned a stack, but the Resource we searched on wasn't in the resulting dataset?
            logger.error("Found stack {} but resource not present {} in account {}".format(stack_name, PhysicalResourceId, self.account_id))
            return(None)

        # Time to get the stack version
        response     = cfn_client.describe_stacks(StackName=output['stack_name'])
        stack = response['Stacks'][0]
        output['Stack'] = stack
        # Iterate down the outputs till we find the key TemplateVersion. That is our version
        output['template_version'] = False
        if 'Outputs' in stack:
            for o in stack['Outputs']:
                if o['OutputKey'] == VersionOutputKey:
                    output['template_version']= o['OutputValue']
                    break
            else:
                output['template_version']= "NotFound"

        # Return the stackname and template_version
        return(output)

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
