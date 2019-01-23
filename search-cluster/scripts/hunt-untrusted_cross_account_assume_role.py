#!/usr/bin/env python3

import boto3
import re
import requests
from requests_aws4auth import AWS4Auth
from elasticsearch import Elasticsearch, RequestsHttpConnection

import json
import os
import time
import datetime
from dateutil import tz

from lib.common import *

import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('elasticsearch').setLevel(logging.WARNING)


# Lambda execution starts here
def main(args, logger):

    region = os.environ['AWS_DEFAULT_REGION']
    service = 'es'
    credentials = boto3.Session().get_credentials()
    awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, service, session_token=credentials.token)

    # host = "https://{}".format(os.environ['ES_DOMAIN_ENDPOINT'])
    host = get_endpoint(args.domain)

    if host is None:
        logger.error(f"Unable to find ES Endpoint for {args.domain}. Aborting....")
        exit(1)


    es = Elasticsearch(
        hosts=[{'host': host, 'port': 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )
    if args.debug:
        logger.info(es.info())

    active_accounts = get_account_ids(status="ACTIVE", table_name=args.account_table)
    suspended_accounts = get_account_ids(status="SUSPENDED", table_name=args.account_table)
    known_accounts = get_account_ids(status="TRUSTED", table_name=args.account_table)
    trusted_accounts = suspended_accounts + active_accounts + known_accounts

    found_counter = 0
    print("Roles that can be assumed from other AWS accounts:")
    index_name = "resources_iam_role"

    query = {
        "query_string": {
                "query": "configuration.AssumeRolePolicyDocument.Statement.Principal.AWS.keyword:*  "
            }
    }

    res = es.search(index=index_name, size=10000, body={"query": query})
    # if args.debug:
    print(f"got {res['hits']['total']} hits from es")

    for hit in res['hits']['hits']:
        if args.inspect:
            print(json.dumps(hit, sort_keys=True, default=str, indent=2))
        doc = hit['_source']

        trusted_principals = []
        for s in doc['configuration']['AssumeRolePolicyDocument']['Statement']:
            if 'AWS' not in s['Principal']:
                continue
            if type(s['Principal']['AWS']) is list:
                for p in s['Principal']['AWS']:
                    if doc['awsAccountId'] in p:
                        continue

                    if not is_principal_trusted(p, trusted_accounts):
                        trusted_principals.append(p)
            else:
                p = s['Principal']['AWS']
                if doc['awsAccountId'] in p:
                    continue
                if not is_principal_trusted(p, trusted_accounts):
                    trusted_principals.append(p)
        try:
            if len(trusted_principals) > 0:
                print(f"\t{doc['awsAccountName']} ({doc['awsAccountId']}) - {doc['configuration']['RoleName']} Trusts {','.join(trusted_principals)}")
                found_counter += 1
        except TypeError as e:
            print(f"TypeError: {e}\n{doc}\n{trusted_principals} ")
            exit(1)

    print(f"Found {found_counter} roles (from {res['hits']['total']})")

    exit(0)

def is_principal_trusted(principal, trusted_accounts):
    if "arn" in principal:
        # We need to extract the account_id
        account_id = principal.split(":")[4]
    else:
        account_id = principal

    if account_id in trusted_accounts:
        return(True)
    else:
        return(False)


def get_endpoint(domain):
    ''' using the boto3 api, gets the URL endpoint for the cluster '''
    es_client = boto3.client('es')

    response = es_client.describe_elasticsearch_domain(DomainName=domain)
    if 'DomainStatus' in response:
        if 'Endpoint' in response['DomainStatus']:
            return(response['DomainStatus']['Endpoint'])

    logger.error("Unable to get ES Endpoint for {}".format(domain))
    return(None)

if __name__ == '__main__':

    # Process Arguments
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", help="print debugging info", action='store_true')
    parser.add_argument("--error", help="print error info only", action='store_true')
    parser.add_argument("--inspect", help="inspect the json elements for the results", action='store_true')
    parser.add_argument("--domain", help="Elastic Search Domain", required=True)
    parser.add_argument("--account_table", help="Account Table Name", required=True)

    args = parser.parse_args()

    # Logging idea stolen from: https://docs.python.org/3/howto/logging.html#configuring-logging
    # create console handler and set level to debug
    ch = logging.StreamHandler()
    if args.debug:
        ch.setLevel(logging.DEBUG)
        logging.getLogger('elasticsearch').setLevel(logging.DEBUG)
    elif args.error:
        ch.setLevel(logging.ERROR)
    else:
        ch.setLevel(logging.INFO)
    # create formatter
    # formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    # add formatter to ch
    ch.setFormatter(formatter)
    # add ch to logger
    logger.addHandler(ch)

    # Wrap in a handler for Ctrl-C
    try:
        rc = main(args, logger)
        print("Lambda executed with {}".format(rc))
    except KeyboardInterrupt:
        exit(1)
