#!/usr/bin/env python3

import boto3
import re
import requests
from requests_aws4auth import AWS4Auth
from elasticsearch import Elasticsearch, RequestsHttpConnection, ElasticsearchException, RequestError

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


# Lambda execution starts here
def main(args, logger):
    print("Creating index {} in {}".format(args.index, args.domain))

    host = get_endpoint(args.domain)
    if host is None:
        print("Failed to get Endpoint. Aborting....")
        exit(1)

    region = os.environ['AWS_DEFAULT_REGION']
    service = 'es'
    credentials = boto3.Session().get_credentials()
    awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, service, session_token=credentials.token)

    es = Elasticsearch(
        hosts=[{'host': host, 'port': 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )
    if args.debug:
        logger.debug(es.info())

    try:
        if not os.path.isdir(args.mapping_dir):
            print(f"Unable to find mapping_dir: {args.mapping_dir}. Aborting....")
            exit(1)

        if os.path.exists(f"{args.mapping_dir}/{args.index}.json"):
            filename = f"{args.mapping_dir}/{args.index}.json"
        elif os.path.exists(f"{args.mapping_dir}/default.json"):
            filename = f"{args.mapping_dir}/default.json"
        else:
            print(f"Unable to find mapping for {args.index}, or a default.json. Aborting....")
            exit(1)

        fh = open(filename, "r")
        mapping_text = fh.read()
    except Exception as e:
        print(f"unable to read mapping file in {args.mapping_dir} for {args.index}: {e}. Aborting....")
        exit(1)

    if args.delete:
        try:
            print(f"Deleting Index {args.index}")
            es.indices.delete(index=args.index)
        except RequestError as e:
            # if e.error == ""
            print(f"Unable to delete index {args.index}: {e}")
            exit(1)
        except ElasticsearchException as e:
            print(f"Unable to delete index {args.index}: {e}")
            exit(1)

    try:
        response = es.indices.create(index=args.index, body=json.loads(mapping_text))
    except ElasticsearchException as e:
        print(f"Failed to create index {args.index}: {e}")
        exit(1)

def get_endpoint(domain):
    ''' using the boto3 api, gets the URL endpoint for the cluster '''
    es_client = boto3.client('es')

    response = es_client.describe_elasticsearch_domain(DomainName=domain)
    if 'DomainStatus' in response:
        if 'Endpoint' in response['DomainStatus']:
            return(response['DomainStatus']['Endpoint'])

    logger.error("Unable to get ES Endpoint for {}".format(domain))
    return(None)




def do_args():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", help="print debugging info", action='store_true')
    parser.add_argument("--error", help="print error info only", action='store_true')

    parser.add_argument("--domain", help="Elastic Search Domain", required=True)
    parser.add_argument("--index", help="Index to create", required=True)
    parser.add_argument("--mapping_dir", help="Directory with mapping files", required=True)
    parser.add_argument("--region", help="AWS Region")
    parser.add_argument("--delete", help="Delete the index before recreating it", action='store_true')

    args = parser.parse_args()

    return(args)

if __name__ == '__main__':

    args = do_args()

    # Logging idea stolen from: https://docs.python.org/3/howto/logging.html#configuring-logging
    # create console handler and set level to debug
    ch = logging.StreamHandler()
    if args.debug:
        ch.setLevel(logging.DEBUG)
    else:
        ch.setLevel(logging.ERROR)

    # create formatter
    # formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    # add formatter to ch
    ch.setFormatter(formatter)
    # add ch to logger
    logger.addHandler(ch)

    # Sanity check region
    if args.region:
        os.environ['AWS_DEFAULT_REGION'] = args.region

    if 'AWS_DEFAULT_REGION' not in os.environ:
        logger.error("AWS_DEFAULT_REGION Not set. Aborting...")
        exit(1)

    main(args, logger)

