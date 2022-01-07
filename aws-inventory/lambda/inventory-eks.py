# Copyright 2019-2020 Turner Broadcasting Inc. / WarnerMedia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import boto3
from botocore.exceptions import ClientError
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

RESOURCE_PATH = "eks/cluster"
TYPE = "AWS::EKS::Cluster"

def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        for r in target_account.get_regions():
            try:
                discover_eks_clusters(target_account, r)
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


def discover_eks_clusters(account, region):
    eks_list = []
    eks_client = account.get_client("eks", region=region)
    response = eks_client.list_clusters()
    while "nextToken" in response:
        for cluster in response.get("clusters"):
            eks_list.append(cluster)
        response = eks_client.list_clusters(nextToken=response.get("nextToken"))
    for cluster in response.get("clusters"):
            eks_list.append(cluster)

    for cluster in eks_list:
        eks_cluster = eks_client.describe_cluster(name=cluster)
        resource_item = {
            "awsAccountId":                 account.account_id,
            "awsAccountName":               account.account_name,
            "resourceType":                 TYPE,
            "configurationItemCaptureTime": str(datetime.datetime.now()),
            "awsRegion":                    region,
            "configuration":                eks_cluster,
            "supplementaryConfiguration":   {},
            "resourceName":                 eks_cluster.get("name"),
            "resourceId":                   f"{account.account_id}-{region}-{eks_cluster.get('name')}",
            "ARN":                          eks_cluster.get("arn"),
            "resourceCreationTime":         eks_cluster.get("createAt"),
            "errors":                       {}
        }
        save_resource_to_s3(RESOURCE_PATH, resource_item['resourceId'], resource_item)

