#!/usr/bin/env python3

import boto3
import re
import requests
from requests_aws4auth import AWS4Auth
from elasticsearch import Elasticsearch, RequestsHttpConnection, ElasticsearchException


import json
import os
import time
import datetime
from dateutil import tz

# from lib.account import *
# from lib.common import *


import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)


# Lambda execution starts here
def main(args, logger):

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


    # Make sure the directory exists
    try:
        os.makedirs(args.output_dir)
    except OSError:
        print ("Creation of the directory %s failed" % args.output_dir)
    else:
        print ("Successfully created the directory %s" % args.output_dir)

    # print(es.indices)
    if not args.index:
        search_index = "*"
    else:
        search_index = args.index
    for index_name in es.indices.get(search_index):
        if not index_name.startswith("resources_"):
            continue
        print("Dumping %s" % index_name)
        response = es.indices.get_mapping(index=index_name)
        mapping = response[index_name]

        # Clean out any tags
        if 'tags' in mapping['mappings']['_doc']['properties']:
            del(mapping['mappings']['_doc']['properties']['tags'])

        file_name = f"{args.output_dir}/{index_name}.json"
        file = open(file_name, "w")
        file.write(json.dumps(mapping, sort_keys=True, indent=2))
        file.close()



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

    # parser.add_argument("--env_file", help="Environment File to source", default="config.env")

    parser.add_argument("--domain", help="Elastic Search Domain", required=True)
    parser.add_argument("--index", help="Ony dump the mapping for this index")
    parser.add_argument("--region", help="AWS Region")
    parser.add_argument("--output_dir", help="Directory to dump all mappings into", required=True)

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

