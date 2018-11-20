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

RESOURCE_PATH = "es/domain"

def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:

        target_account = AWSAccount(message['account_id'])

        regions = target_account.get_regions()
        if 'region' in message:
            regions = [ message['region'] ]

        # describe ES Domains
        for r in regions:
            es_client = target_account.get_client('es', region=r)

            for domain_name in list_domains(es_client, target_account, r):
                response = es_client.describe_elasticsearch_domain(DomainName=domain_name)
                domain = response['DomainStatus']

                if domain['AccessPolicies']:
                    # The ES Domains' Access policy is returned as a string. Here we parse the json and reapply it to the dict
                    domain['AccessPolicies']  = json.loads(domain['AccessPolicies'])

                domain['region']        = r
                domain['resource_type'] = "es-cluster"
                domain['account_id']    = target_account.account_id
                domain['account_name']  = target_account.account_name
                domain['last_seen']     = str(datetime.datetime.now(tz.gettz('US/Eastern')))
                object_name = "{}-{}-{}".format(domain_name, r, target_account.account_id)
                save_resource_to_s3(RESOURCE_PATH, object_name, domain)

    except AssumeRoleError as e:
        logger.error("Unable to assume role into account {}({})".format(target_account.account_name, target_account.account_id))
        return()
    except ClientError as e:
        logger.error("AWS Error getting info for {}: {}".format(target_account.account_name, e))
        return()
    except Exception as e:
        logger.error("{}\nMessage: {}\nContext: {}".format(e, message, vars(context)))
        raise


def list_domains(es_client, target_account, region):
    domain_names = []
    response = es_client.list_domain_names() # This call doesn't support paganiation
    if 'DomainNames' not in response:
        logger.info("No ElasticSearch domains returned by list_domain_names() for {}({}) in {}".format(target_account.account_name, target_account.account_id, region))
    else:
        for d in response['DomainNames']:
            domain_names.append(d['DomainName'])
    return(domain_names)
