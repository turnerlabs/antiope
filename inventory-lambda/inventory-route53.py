
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
logger.setLevel(logging.DEBUG)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)


def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        discover_domains(target_account)
        discover_zones(target_account)

    except AssumeRoleError as e:
        logger.error("Unable to assume role into account {}({})".format(target_account.account_name, target_account.account_id))
        return()
    except ClientError as e:
        logger.error("AWS Error getting info for {}: {}".format(target_account.account_name, e))
        return()
    except Exception as e:
        logger.error("{}\nMessage: {}\nContext: {}".format(e, message, vars(context)))
        raise

def discover_domains(account):
    '''
        Gathers all the Route53Domains registered domains
    '''
    domains = []

    # Not all Public IPs are attached to instances. So we use ec2 describe_network_interfaces()
    # All results are saved to S3. Public IPs and metadata go to DDB (based on the the presense of PublicIp in the Association)
    route53_client = account.get_client('route53domains')
    response = route53_client.list_domains()
    while 'NextPageMarker' in response:  # Gotta Catch 'em all!
        domains += response['Domains']
        response = route53_client.list_domains(Marker=response['NextPageMarker'])
    domains += response['Domains']

    for d in domains:

        # Get the real juicy details
        domain = route53_client.get_domain_detail(DomainName=d['DomainName'])

        del domain['ResponseMetadata'] # Remove response metadata. Not needed

        # Now decorate with the info needed to find it
        domain['account_id']       = account.account_id
        domain['account_name']     = account.account_name
        # And the one bit of info that only list domains had.
        domain['TransferLock']     = d['TransferLock']

        # Not sure why Route53 product team makes me do a special call for tags.
        response = route53_client.list_tags_for_domain(DomainName=d['DomainName'])
        if 'TagList' in response:
            domain['Tags'] = response['TagList']

        # Need to make sure the resource name is unique and service identifiable.
        resource_name = "domain-{}".format(domain['DomainName'])
        save_resource_to_s3("route53", resource_name, domain)

def discover_zones(account):
    '''
        Queries AWS to determine what Route53 Zones are hosted in an AWS Account
    '''
    zones = []

    # Not all Public IPs are attached to instances. So we use ec2 describe_network_interfaces()
    # All results are saved to S3. Public IPs and metadata go to DDB (based on the the presense of PublicIp in the Association)
    route53_client = account.get_client('route53')
    response = route53_client.list_hosted_zones()
    while 'IsTruncated' in response and response['IsTruncated'] is True:  # Gotta Catch 'em all!
        zones += response['HostedZones']
        response = route53_client.list_hosted_zones(Marker=response['NextMarker'])
    zones += response['HostedZones']

    for zone in zones:
        zone['account_id']       = account.account_id
        zone['account_name']     = account.account_name
        zone['last_updated']     = str(datetime.datetime.now(tz.gettz('US/Eastern')))

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
            zone['AuthorizedVPCs'] = response['VPCs']


        # Need to make sure the resource name is unique and service identifiable.
        # Zone Ids look like "/hostedzone/Z2UFNORDFDSFTZ"
        resource_name = "hostedzone-{}".format(zone['Id'].split("/")[2])
        save_resource_to_s3("route53", resource_name, zone)



def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))