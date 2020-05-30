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
logging.getLogger('elasticsearch').setLevel(logging.WARNING)


# Lambda execution starts here
def main(args, logger):
    logger.debug(f"Running {args.action} against {args.domain}")

    host = get_endpoint(args.domain, args.region)
    if host is None:
        print("Failed to get Endpoint. Aborting....")
        exit(1)

    region = os.environ['AWS_DEFAULT_REGION']
    service = 'es'
    credentials = boto3.Session().get_credentials()
    awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, service, session_token=credentials.token)

    if args.action == "register":
        if not args.role_arn:
            print("No Role ARN specified. Aborting....")
            exit(1)
        if not args.bucket:
            print("No Bucket specified. Aborting....")
            exit(1)
        register_repo(args, awsauth, host)

    elif args.action == "list":
        list_snapshots(args, awsauth, host)

    elif args.action == "status":
        if not is_snapshot_in_progress(args, awsauth, host):
            print("No Snapshots in progress")

    elif args.action == "take":
        if not args.snapshot_name:
            print("No Snapshot name specified. Aborting....")
            exit(1)
        if is_snapshot_in_progress(args, awsauth, host):
            print("Snapshot is in progress. Aborting...")
            exit(1)
        take_snapshot(args, awsauth, host)

    elif args.action == "restore":
        if not args.snapshot_name:
            print("No Snapshot name specified. Aborting....")
            exit(1)
        if is_snapshot_in_progress(args, awsauth, host):
            print("Snapshot is in progress. Aborting...")
            exit(1)
        restore_snapshot(args, awsauth, host)

    else:
        print("Invalid Action")

def take_snapshot(args, awsauth, host):
    url = f"https://{host}/_snapshot/antiope-snapshot-repo/{args.snapshot_name}"
    try:
        logger.debug(f"PUT to {url}")
        r = requests.put(url, auth=awsauth)
    except Exception as e:
        print(f"Error: {e}")
        exit(1)

    if r.status_code == 200:
        print("Success")
        exit(0)
    else:
        print(f"Error {r.status_code}: {r.text}")
        exit(1)

def restore_snapshot(args, awsauth, host):
    url = f"https://{host}/_snapshot/antiope-snapshot-repo/{args.snapshot_name}/_restore"
    try:
        logger.debug(f"POST to {url}")
        r = requests.post(url, auth=awsauth)
    except Exception as e:
        print(f"Error: {e}")
        exit(1)

    if r.status_code == 200:
        print("Success")
        exit(0)
    else:
        print(f"Error {r.status_code}: {r.text}")
        exit(1)


def register_repo(args, awsauth, host):
    path = '/_snapshot/antiope-snapshot-repo' # the Elasticsearch API endpoint
    url = "https://" + host + path

    payload = {
      "type": "s3",
      "settings": {
        "bucket": args.bucket,
        "role_arn": args.role_arn,
        "base_path": "ElasticSearchSnapshots",
        "server_side_encryption": True
      }
    }

    if args.region == "us-east-1":
        payload['settings']['endpoint'] = "s3.amazonaws.com"
    else:
        payload['settings']['region'] = args.region

    headers = {"Content-Type": "application/json"}
    try:
        logger.debug(f"PUT to {url}")
        logger.debug(f"Payload: {json.dumps(payload)}")
        r = requests.put(url, auth=awsauth, json=payload, headers=headers)
    except Exception as e:
        print(f"Error: {e}")
        exit(1)

    if r.status_code == 200:
        print("Success")
        exit(0)
    else:
        print(f"Error {r.status_code}: {r.text}")
        exit(1)

#
# Run a simple GET against the cluster and return the json results as a dict
#
def es_get(args, awsauth, host, path):
    url = "https://" + host + path
    logger.debug(f"GET to {url}")
    r = requests.get(url, auth=awsauth)
    logger.debug(r.status_code)
    response = json.loads(r.text)
    logger.debug(json.dumps(response, sort_keys=True, indent=2))
    return(response)


def is_snapshot_in_progress(args, awsauth, host):
    path = '/_snapshot/_status'
    response = es_get(args, awsauth, host, path)
    if len(response['snapshots']) == 0:
        return(False)
    else:
        for s in response['snapshots']:
            print(f"Snapshot {s['snapshot']} in {s['repository']} is state {s['state']}")
        return(True)

def list_snapshots(args, awsauth, host):
    path = '/_snapshot/antiope-snapshot-repo/_all?pretty' # the Elasticsearch API endpoint
    response = es_get(args, awsauth, host, path)
    for s in response['snapshots']:
        print(f"Snapshot {s['snapshot']} taken at {s['start_time']} is state {s['state']}")


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
    parser.add_argument("--domain", help="Elastic Search Domain", required=True)
    parser.add_argument("--region", help="AWS Region", default=os.environ['AWS_DEFAULT_REGION'])
    parser.add_argument("--bucket", help="Snapshot Bucket")
    parser.add_argument("--role-arn", help="Snapshot Role Arn")
    parser.add_argument("--action", help="Action to take", required=True, choices=['register', 'list', 'status', 'take', 'restore'])
    parser.add_argument("--snapshot-name", help="Snapshot name")

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
    formatter = logging.Formatter('%(levelname)s - %(message)s')
    # add formatter to ch
    ch.setFormatter(formatter)
    # add ch to logger
    logger.addHandler(ch)

    # # Sanity check region
    # if args.region:
    #     os.environ['AWS_DEFAULT_REGION'] = args.region

    # if 'AWS_DEFAULT_REGION' not in os.environ:
    #     logger.error("AWS_DEFAULT_REGION Not set. Aborting...")
    #     exit(1)

    main(args, logger)

