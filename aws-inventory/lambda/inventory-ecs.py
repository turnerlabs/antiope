import boto3
from botocore.exceptions import ClientError, ParamValidationError
import json
import os
import time
from datetime import datetime, timezone
from dateutil import tz

from antiope.aws_account import *
from common import *

import logging
logger = logging.getLogger()
logger.setLevel(getattr(logging, os.getenv('LOG_LEVEL', default='INFO')))
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

CLUSTER_RESOURCE_PATH = "ecs/cluster"
TASK_RESOURCE_PATH = "ecs/task"


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
            try:
                ecs_client = target_account.get_client('ecs', region=r)
                for cluster_arn in list_clusters(ecs_client):
                    cluster = ecs_client.describe_clusters(clusters=[cluster_arn], include=['STATISTICS', 'TAGS'])['clusters'][0]

                    cluster_item = {}
                    cluster_item['awsAccountId']                   = target_account.account_id
                    cluster_item['awsAccountName']                 = target_account.account_name
                    cluster_item['resourceType']                   = "AWS::ECS::Cluster"
                    cluster_item['source']                         = "Antiope"
                    cluster_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
                    cluster_item['awsRegion']                      = r
                    cluster_item['configuration']                  = cluster
                    if 'tags' in cluster:
                        cluster_item['tags']                       = parse_ecs_tags(cluster['tags'])
                    cluster_item['supplementaryConfiguration']     = {}
                    cluster_item['resourceId']                     = "{}-{}".format(cluster['clusterName'], target_account.account_id)
                    cluster_item['resourceName']                   = cluster['clusterName']
                    cluster_item['ARN']                            = cluster['clusterArn']
                    cluster_item['errors']                         = {}
                    save_resource_to_s3(CLUSTER_RESOURCE_PATH, cluster_item['resourceId'], cluster_item)

                    for task_arn in list_tasks(ecs_client, cluster_arn):

                        # Lambda's boto doesn't yet support this API Feature
                        try:
                            task = ecs_client.describe_tasks(cluster=cluster_arn, tasks=[task_arn], include=['TAGS'])['tasks'][0]
                        except ParamValidationError as e:
                            import botocore
                            logger.error(f"Unable to fetch Task Tags - Lambda Boto3 doesn't support yet. Boto3: {boto3.__version__} botocore: {botocore.__version__}")
                            task = ecs_client.describe_tasks(cluster=cluster_arn, tasks=[task_arn])['tasks'][0]

                        task_item = {}
                        task_item['awsAccountId']                   = target_account.account_id
                        task_item['awsAccountName']                 = target_account.account_name
                        task_item['resourceType']                   = "AWS::ECS::Task"
                        task_item['source']                         = "Antiope"
                        task_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
                        task_item['awsRegion']                      = r
                        task_item['configuration']                  = task
                        if 'tags' in task:
                            task_item['tags']                       = parse_ecs_tags(task['tags'])
                        task_item['supplementaryConfiguration']     = {}
                        task_item['resourceId']                     = "{}-{}".format(task['taskDefinitionArn'].split('/')[-1], target_account.account_id)
                        task_item['resourceName']                   = task['taskDefinitionArn'].split('/')[-1]
                        task_item['ARN']                            = task['taskArn']
                        task_item['errors']                         = {}
                        save_resource_to_s3(TASK_RESOURCE_PATH, task_item['resourceId'], task_item)
            except ClientError as e:
                # Move onto next region if we get access denied. This is probably SCPs
                if e.response['Error']['Code'] == 'AccessDeniedException':
                    logger.error(f"AccessDeniedException for region {r} in function {context.function_name} for {target_account.account_name}({target_account.account_id})")
                    continue
                else:
                    raise  # pass on to the next handlier


    except AntiopeAssumeRoleError as e:
        logger.error("Unable to assume role into account {}({})".format(target_account.account_name, target_account.account_id))
        return()
    except ClientError as e:
        if e.response['Error']['Code'] == 'UnauthorizedOperation':
            logger.error("Antiope doesn't have proper permissions to this account")
            return(event)
        logger.critical("AWS Error getting info for {}: {}".format(message['account_id'], e))
        capture_error(message, context, e, "ClientError for {}: {}".format(message['account_id'], e))
        raise
    except Exception as e:
        logger.critical("{}\nMessage: {}\nContext: {}".format(e, message, vars(context)))
        capture_error(message, context, e, "General Exception for {}: {}".format(message['account_id'], e))
        raise


def list_tasks(ecs_client, cluster_arn):
    task_arns = []
    response = ecs_client.list_tasks(cluster=cluster_arn)
    while 'nextToken' in response:
        task_arns += response['taskArns']
        response = ecs_client.list_tasks(cluster=cluster_arn, nextToken=response['nextToken'])
    task_arns += response['taskArns']
    return(task_arns)


def list_clusters(ecs_client):
    cluster_arns = []
    response = ecs_client.list_clusters()
    while 'nextToken' in response:
        cluster_arns += response['clusterArns']
        response = ecs_client.list_clusters(nextToken=response['nextToken'])
    cluster_arns += response['clusterArns']
    return(cluster_arns)


def parse_ecs_tags(tagset):
    """Convert the tagset as returned by AWS into a normal dict of {"tagkey": "tagvalue"}"""
    output = {}
    for tag in tagset:
        output[tag['key']] = tag['value']
    return(output)
