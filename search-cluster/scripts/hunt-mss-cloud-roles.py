#!/usr/bin/env python3
import boto3
from requests_aws4auth import AWS4Auth
from elasticsearch import Elasticsearch, RequestsHttpConnection
import os

import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('elasticsearch').setLevel(logging.WARNING)


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

    print("Getting list of all aws-admin-IAMrolesRole Cloudformation Stacks")

    index_name = "resources_cloudformation_stack"

    query = {
        "query_string": {
            "query": "configuration.StackName: \"aws-admin-IAMrolesRole\""
        }
    }

    res = es.search(index=index_name, size=10000, body={"query": query})
    template_version_dict = {} # template versions are stored here
    for hit in res['hits']['hits']:
        template_version = hit["_source"]["configuration"]["Outputs"][0]["OutputValue"]
        template_version_array = template_version_dict.get(template_version, [])

        account_Id = hit["_source"]["awsAccountId"]
        account_name = hit["_source"]["awsAccountName"]

        data_string = account_Id + " " + account_name + " "+ template_version

        template_version_array.append(data_string)
        template_version_dict[template_version] = template_version_array

    for temp_version in template_version_dict.keys():
        print("================== Template Version ", temp_version, " ===========================")
        temp_version_array = template_version_dict[temp_version]

        for account in temp_version_array:
            print("  "+ account)

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
