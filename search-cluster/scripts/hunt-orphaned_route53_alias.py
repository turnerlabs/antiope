#!/usr/bin/env python3

import boto3
from botocore.exceptions import ClientError

import re
import requests
from requests_aws4auth import AWS4Auth
from elasticsearch import Elasticsearch, RequestsHttpConnection


import json
import os
import time
import datetime
from dateutil import tz

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

    print("Getting list of all known buckets")
    known_buckets = []
    index_name = "resources_s3_bucket"
    query = {"match_all": {}}
    res = es.search(index=index_name, size=10000, body={"query": query})
    for hit in res['hits']['hits']:
        known_buckets.append(hit['_source']['configuration']['Name'])


    print("Analying Route 53 Record Sets and identifying all s3 buckets ownership")
    index_name = "resources_route53_hostedzone"

    query = {
        "query_string": {
                "query": "supplementaryConfiguration.ResourceRecordSets.AliasTarget.DNSName : \"s3-website\""
            }
    }

    res = es.search(index=index_name, size=10000, body={"query": query})

    bad_count = 0
    escalate_count = 0

    for hit in res['hits']['hits']:
        if args.inspect:
            print(json.dumps(hit, sort_keys=True, default=str, indent=2))
        doc = hit['_source']

        for rr in doc['supplementaryConfiguration']['ResourceRecordSets']:
            if 'AliasTarget' not in rr:
                continue
            if "s3-website" not in rr['AliasTarget']['DNSName']:
                continue
            bucket_name = rr['Name'][:-1]
            if bucket_name not in known_buckets:
                bad_count += 1
                if does_bucket_exist(bucket_name):
                    print(f"\t{doc['awsAccountName']} ({doc['awsAccountId']}) ZoneName: {doc['resourceName']} - Record: {bucket_name} - Aliased as: {rr['AliasTarget']['DNSName']} - BUCKET EXISTS")
                    escalate_count += 1
                else:
                    print(f"\t{doc['awsAccountName']} ({doc['awsAccountId']}) ZoneName: {doc['resourceName']} - Record: {bucket_name} - Aliased as: {rr['AliasTarget']['DNSName']} - Bucket is unclaimed")

    print(f"Found {res['hits']['total']} Zones. {bad_count} are potentially bad. {escalate_count} need to be treated as a security incident")

    exit(0)


def does_bucket_exist(bucket_name):
    try:
        client = boto3.client('s3')
        response = client.get_bucket_location(
            Bucket=bucket_name
        )
        return(True)
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchBucket':
            return(False)
        else:
            return(True)



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
