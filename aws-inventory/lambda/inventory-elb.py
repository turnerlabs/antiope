
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

V1_RESOURCE_PATH = "elb/loadbalancer"
V2_RESOURCE_PATH = "elbv2/loadbalancer"
V1_TYPE = "AWS::ElasticLoadBalancing::LoadBalancer"
V2_TYPE = "AWS::ElasticLoadBalancingV2::LoadBalancer"


def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        for r in target_account.get_regions():
            discover_elbv1(target_account, r)
            discover_elbv2(target_account, r)

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


def discover_elbv1(account, region):
    '''Discover all Classic Loadbalancers (ELBs)'''

    elbs = []

    elb_client = account.get_client('elb', region=region)
    response = elb_client.describe_load_balancers()
    while 'NextMarker' in response:  # Gotta Catch 'em all!
        elbs += response['LoadBalancerDescriptions']
        response = elb_client.describe_load_balancers(Marker=response['NextMarker'])
    elbs += response['LoadBalancerDescriptions']

    for elb in elbs:
        name = elb['LoadBalancerName']

        resource_item = {}
        resource_item['awsAccountId']                   = account.account_id
        resource_item['awsAccountName']                 = account.account_name
        resource_item['resourceType']                   = V1_TYPE
        resource_item['source']                         = "Antiope"
        resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
        resource_item['awsRegion']                      = region
        resource_item['configuration']                  = elb
        resource_item['supplementaryConfiguration']     = {}
        resource_item['resourceName']                   = elb['LoadBalancerName']
        resource_item['resourceId']                     = f"{account.account_id}-{region}-{elb['LoadBalancerName']}"
        resource_item['resourceCreationTime']           = elb['CreatedTime']
        resource_item['errors']                         = {}

        # To Fix - throttling occurs here
        # policies = elb_client.describe_load_balancer_policies(LoadBalancerName=name)
        # resource_item['supplementaryConfiguration']['PolicyDescriptions'] = policies['PolicyDescriptions']

        # attrib = elb_client.describe_load_balancer_attributes(LoadBalancerName=name)
        # resource_item['supplementaryConfiguration']['LoadBalancerAttributes'] = attrib['LoadBalancerAttributes']

        try:
            tags = elb_client.describe_tags(LoadBalancerNames=[name])
            resource_item['tags'] = parse_tags(tags['TagDescriptions'][0]['Tags'])
        except (ClientError, KeyError, IndexError):
            pass  # If Tags aren't present or whatever, just ignore

        save_resource_to_s3(V1_RESOURCE_PATH, resource_item['resourceId'], resource_item)


def discover_elbv2(account, region):
    '''Discover all Version 2 Loadbalancers (ALBs and NLBs)'''

    elbs = []

    elb_client = account.get_client('elbv2', region=region)
    response = elb_client.describe_load_balancers()
    while 'NextMarker' in response:  # Gotta Catch 'em all!
        elbs += response['LoadBalancers']
        response = elb_client.describe_load_balancers(Marker=response['NextMarker'])
    elbs += response['LoadBalancers']

    for elb in elbs:
        arn = elb['LoadBalancerArn']

        resource_item = {}
        resource_item['awsAccountId']                   = account.account_id
        resource_item['awsAccountName']                 = account.account_name
        resource_item['resourceType']                   = V2_TYPE
        resource_item['source']                         = "Antiope"
        resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
        resource_item['awsRegion']                      = region
        resource_item['configuration']                  = elb
        resource_item['supplementaryConfiguration']     = {}
        resource_item['resourceName']                   = elb['LoadBalancerName']
        resource_item['resourceId']                     = f"{account.account_id}-{region}-{elb['LoadBalancerName']}"
        resource_item['ARN']                            = arn
        resource_item['resourceCreationTime']           = elb['CreatedTime']
        resource_item['errors']                         = {}

        # To Fix - throttling occurs here
        attrib = elb_client.describe_load_balancer_attributes(LoadBalancerArn=arn)
        resource_item['supplementaryConfiguration']['Attributes'] = attrib['Attributes']

        try:
            tags = elb_client.describe_tags(ResourceArns=[arn])
            resource_item['tags'] = parse_tags(tags['TagDescriptions'][0]['Tags'])
        except (ClientError, KeyError, IndexError):
            pass  # If Tags aren't present or whatever, just ignore

        # Currently Not collected:
        # 1) Target Groups (describe_target_groups) & attributes (describe_target_group_attributes)
        # 2) Listeners (describe_listeners)
        # 3) Listener Certificates (describe_listener_certificates)
        # 4) Listener Rules (describe_rules)

        save_resource_to_s3(V2_RESOURCE_PATH, resource_item['resourceId'], resource_item)

