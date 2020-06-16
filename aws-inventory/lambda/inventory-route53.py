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

DOMAIN_RESOURCE_PATH = "route53/domain"
ZONE_RESOURCE_PATH = "route53/hostedzone"


def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        discover_domains(target_account)
        discover_zones(target_account)

    except AntiopeAssumeRoleError as e:
        logger.error("Unable to assume role into account {}({})".format(target_account.account_name, target_account.account_id))
        return()
    except ClientError as e:
        logger.critical("AWS Error getting info for {}: {}".format(message['account_id'], e))
        capture_error(message, context, e, "ClientError for {}: {}".format(message['account_id'], e))
        raise
    except Exception as e:
        logger.critical("{}\nMessage: {}\nContext: {}".format(e, message, vars(context)))
        capture_error(message, context, e, "General Exception for {}: {}".format(message['account_id'], e))
        raise


def discover_domains(account):
    '''
        Gathers all the Route53Domains registered domains
    '''
    domains = []

    # Not all Public IPs are attached to instances. So we use ec2 describe_network_interfaces()
    # All results are saved to S3. Public IPs and metadata go to DDB (based on the the presense of PublicIp in the Association)
    route53_client = account.get_client('route53domains', region="us-east-1")  # Route53 Domains is only available in us-east-1

    try:
        response = route53_client.list_domains()
    except ClientError as e:
        if e.response['Error']['Code'] == 'ThrottlingException':
            time.sleep(1)
            response = route53_client.list_domains()
        else:
            raise

    while 'NextPageMarker' in response:  # Gotta Catch 'em all!
        domains += response['Domains']
        try:
            response = route53_client.list_domains(Marker=response['NextPageMarker'])
        except ClientError as e:
            if e.response['Error']['Code'] == 'ThrottlingException':
                time.sleep(1)
                response = route53_client.list_domains(Marker=response['NextPageMarker'])
            else:
                raise

    domains += response['Domains']

    for d in domains:

        resource_item = {}
        resource_item['awsAccountId']                   = account.account_id
        resource_item['awsAccountName']                 = account.account_name
        resource_item['resourceType']                   = "AWS::Route53::Domain"
        resource_item['source']                         = "Antiope"

        # Get the real juicy details
        # Throttling/API Limit Info:
        # https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/DNSLimitations.html#limits-api-requests-route-53
        domain = route53_client.get_domain_detail(DomainName=d['DomainName'])
        del domain['ResponseMetadata']  # Remove response metadata. Not needed

        resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
        resource_item['configuration']                  = domain
        resource_item['supplementaryConfiguration']     = {}
        resource_item['resourceId']                     = domain['DomainName']
        resource_item['resourceName']                   = domain['DomainName']
        resource_item['resourceCreationTime']           = domain['CreationDate']
        resource_item['errors']                         = {}

        # And the one bit of info that only list domains had.
        resource_item['supplementaryConfiguration']['TransferLock']     = d['TransferLock']

        # Not sure why Route53 product team makes me do a special call for tags.
        response = route53_client.list_tags_for_domain(DomainName=d['DomainName'])
        if 'TagList' in response:
            resource_item['Tags'] = response['TagList']

        # Need to make sure the resource name is unique and service identifiable.
        save_resource_to_s3(DOMAIN_RESOURCE_PATH, resource_item['resourceId'], resource_item)
        time.sleep(1) # To avoid throttling issues


def discover_zones(account):
    '''
        Queries AWS to determine what Route53 Zones are hosted in an AWS Account
    '''
    zones = []

    # Not all Public IPs are attached to instances. So we use ec2 describe_network_interfaces()
    # All results are saved to S3. Public IPs and metadata go to DDB (based on the the presense of PublicIp in the Association)
    route53_client = account.get_client('route53')

    # Route53 Describe calls have a very low API limit
    try:
        response = route53_client.list_hosted_zones()
    except ClientError as e:
        if e.response['Error']['Code'] == 'ThrottlingException':
            time.sleep(1)
            response = route53_client.list_hosted_zones()
        else:
            raise

    while 'IsTruncated' in response and response['IsTruncated'] is True:  # Gotta Catch 'em all!

        # Process this batch
        for zone in response['HostedZones']:
            process_zone(zone, account, route53_client)

        # Try and get some more
        try:
            response = route53_client.list_hosted_zones(Marker=response['NextMarker'])
        except ClientError as e:
            if e.response['Error']['Code'] == 'ThrottlingException':
                time.sleep(1)
                response = route53_client.list_hosted_zones(Marker=response['NextMarker'])
            else:
                raise

    # Finish Up
    for zone in response['HostedZones']:
        process_zone(zone, account, route53_client)


def process_zone(zone, account, route53_client):

    resource_item = {}
    resource_item['awsAccountId']                   = account.account_id
    resource_item['awsAccountName']                 = account.account_name
    resource_item['resourceType']                   = "AWS::Route53::HostedZone"
    resource_item['source']                         = "Antiope"

    resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
    resource_item['configuration']                  = zone
    # resource_item['tags']                           = FIXME
    resource_item['supplementaryConfiguration']     = {}
    # Need to make sure the resource name is unique and service identifiable.
    # Zone Ids look like "/hostedzone/Z2UFNORDFDSFTZ"
    resource_item['resourceId']                     = zone['Id'].split("/")[2]
    resource_item['resourceName']                   = zone['Name']
    resource_item['errors']                         = {}

    # # Not sure why Route53 product team makes me do a special call for tags.
    # response = route53_client.list_tags_for_resource(
    #     ResourceType='hostedzone',
    #     ResourceId=zone['Id']
    # )
    # if 'ResourceTagSet' in response and 'Tags' in response['ResourceTagSet']:
    #     zone['Tags'] = response['ResourceTagSet']['Tags']

    # This also looks interesting from a data-leakage perspective
    response = route53_client.list_vpc_association_authorizations(HostedZoneId=zone['Id'])
    if 'VPCs' in response:
        resource_item['supplementaryConfiguration']['AuthorizedVPCs'] = response['VPCs']

    # This currently overloads the Route53 API Limits and exceeds Lambda Timeouts.
    # resource_item['supplementaryConfiguration']['ResourceRecordSets'] = get_resource_records(route53_client, zone['Id'])
    # resource_item['supplementaryConfiguration']['ResourceRecordSetCount'] = len(resource_item['supplementaryConfiguration']['ResourceRecordSets'])

    save_resource_to_s3(ZONE_RESOURCE_PATH, resource_item['resourceId'], resource_item)


def get_resource_records(route53_client, hostedzone_id):
    # Route 53 Resource Limits: https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/DNSLimitations.html#limits-api-requests-route-53
    # Maxitems can be 1000, frequency is hardlimited to 5 reqs per sec. Antiope will sleep 1 between calls

    rr_set = []
    response = route53_client.list_resource_record_sets(
        HostedZoneId=hostedzone_id,
        MaxItems="1000"
    )
    while response['IsTruncated']:
        rr_set += response['ResourceRecordSets']
        time.sleep(1)
        response = route53_client.list_resource_record_sets(
            HostedZoneId=hostedzone_id,
            MaxItems="1000",
            StartRecordName=response['NextRecordName']
        )
    rr_set += response['ResourceRecordSets']
    return(rr_set)
