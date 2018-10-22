import boto3
from botocore.exceptions import ClientError

import json
import os
import time
import datetime
from dateutil import tz

from lib.account import *
from lib.common import *

import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)

CLUSTER_RESOURCE_PATH = "ecs/cluster"
TASK_RESOURCE_PATH = "ecs/task"

def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:

        target_account = AWSAccount(message['account_id'])
        s3_client = boto3.client('s3')

        regions = target_account.get_regions()
        if 'region' in message:
            regions = [ message['region'] ]

        # describe ec2 instances
        for r in regions:
            ecs_client = target_account.get_client('ecs', region=r)

            for cluster_arn in list_clusters(ecs_client):
                cluster = ecs_client.describe_clusters(clusters=[cluster_arn], include=['STATISTICS'] )['clusters'][0]
                cluster['account_id'] = message['account_id']
                cluster['region'] = r
                cluster_name = "{}-{}".format(cluster['clusterName'], target_account.account_id)
                save_resource_to_s3(CLUSTER_RESOURCE_PATH, cluster_name, cluster)

                for task_arn in list_tasks(ecs_client, cluster_arn):
                    task = ecs_client.describe_tasks(cluster=cluster_arn, tasks=[task_arn])['tasks'][0]
                    task['account_id'] = message['account_id']
                    task['region'] = r
                    task_name = "{}-{}".format(task['taskDefinitionArn'].split('/')[-1], target_account.account_id)
                    save_resource_to_s3(TASK_RESOURCE_PATH, task_name, task)


    except AssumeRoleError as e:
        logger.error("Unable to assume role into account {}({})".format(target_account.account_name, target_account.account_id))
        return()
    except ClientError as e:
        logger.error("AWS Error getting info for {}: {}".format(target_account.account_name, e))
        return()
    except Exception as e:
        logger.error("{}\nMessage: {}\nContext: {}".format(e, message, vars(context)))
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
