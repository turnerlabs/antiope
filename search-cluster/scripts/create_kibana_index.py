#!/usr/bin/env python3

from dateutil import tz
from elasticsearch import Elasticsearch, RequestsHttpConnection, ElasticsearchException, RequestError, NotFoundError
from requests_aws4auth import AWS4Auth
import boto3
import datetime
import json
import os
import re
import requests
import time

import logging
logger = logging.getLogger()
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('elasticsearch').setLevel(logging.ERROR)


# Lambda execution starts here
def main(args, logger):

    host = get_endpoint(args.domain, args.region)
    if host is None:
        print("Failed to get Endpoint. Aborting....")
        exit(1)

    region = os.environ['AWS_DEFAULT_REGION']
    service = 'es'
    credentials = boto3.Session().get_credentials()
    awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, service, session_token=credentials.token)
    headers = { "Content-Type": "application/json" }

    es = Elasticsearch(
        hosts=[{'host': host, 'port': 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )
    if args.debug:
        logger.debug(es.info())

    doc = {
        "index-pattern": {
            "timeFieldName": "configurationItemCaptureTime"
          },
          "type": "index-pattern"
        }


    # print(es.indices)
    if not args.index:
        search_index = "resources_*"
    else:
        search_index = args.index
    for index_name in es.indices.get(search_index):
        print(f"Index: {index_name}")
        doc['index-pattern']['title'] = index_name

        es.index(index=".kibana", doc_type="doc", id=f"index-pattern:{index_name}", body=doc)



def get_endpoint(domain, region):
    ''' using the boto3 api, gets the URL endpoint for the cluster '''
    es_client = boto3.client('es', region_name=region)

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

    # parser.add_argument("--env_file", help="Environment File to source", default="config.env")

    parser.add_argument("--domain", help="Elastic Search Domain", required=True)
    parser.add_argument("--index", help="Ony dump the mapping for this index")
    parser.add_argument("--region", help="AWS Region")

    args = parser.parse_args()

    return(args)

if __name__ == '__main__':

    args = do_args()

    # Logging idea stolen from: https://docs.python.org/3/howto/logging.html#configuring-logging
    # create console handler and set level to debug
    ch = logging.StreamHandler()
    if args.error:
        logger.setLevel(logging.ERROR)
    elif args.debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

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

