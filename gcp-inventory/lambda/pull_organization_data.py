import boto3
from botocore.exceptions import ClientError

from googleapiclient import discovery
from oauth2client.service_account import ServiceAccountCredentials

from gcp_lib.common import *

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
    project_table = dynamodb.Table(os.environ['PROJECT_TABLE'])

    credential_info = get_gcp_creds(os.environ['GCP_SECRET_NAME'])
    if credential_info is None:
        raise Exception("Unable to extract GCP Credentials. Aborting...")

    project_list = get_projects(credential_info)
    if project_list is None:
        raise Exception("No Projects found. Aborting...")

    # print(project_list)
    for p in project_list:
        create_or_update_project(p, project_table)

    event['project_list'] = project_list
    return(event)

# end handler()

##############################################


def get_projects(credential_info):
    """
    Given a credential set, write to DDB table, publish to SNS topic, and return
    a list of projects for a given account.
    """

    project_list = []
    try:
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(credential_info)
        service = discovery.build('cloudresourcemanager', 'v1', credentials=credentials, cache_discovery=False )
    except Exception as e:
        logger.critical(f"Error during Credential and Service creation: {e}")
        return(None)

    request = service.projects().list()
    while request is not None:
        response = request.execute()
        for project in response['projects']:
            project_list.append(project)

        request = service.projects().list_next(
                      previous_request=request,
                      previous_response=response
                  )

    return(project_list)


def create_or_update_project(project, project_table):
    logger.info(u"Adding project {} with name {} and number {}".format(project[u'projectId'], project[u'name'], project[u'projectNumber']))

    try:
        response = project_table.update_item(
                Key= {'projectId': project['projectId'] },
                UpdateExpression="set projectName=:name, lifecycleState=:lifecycleState, createTime=:createTime, projectNumber=:projectNumber, parent=:parent, labels=:labels",
                ExpressionAttributeValues={
                    ':name':            project['name'],
                    ':lifecycleState':  project['lifecycleState'],
                    ':createTime':      project['createTime'],
                    ':projectNumber':   project['projectNumber'],
                    ':parent':          project['parent'],
                    ':labels':          project['labels'],
                }
            )

    except ClientError as e:
        raise AccountUpdateError(u"Unable to create {}: {}".format(project[u'name'], e))
    except KeyError as e:
        logger.critical(f"Project {project['projectId']} is missing a key: {e}")


class AccountUpdateError(Exception):
    '''raised when an update to DynamoDB Fails'''
