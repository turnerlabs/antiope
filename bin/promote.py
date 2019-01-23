#!/usr/bin/env python3

import boto3
from botocore.exceptions import ClientError
import os
import sys
import json
from pprint import pprint
import os.path

import logging
logger = logging.getLogger()
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

components = ["cognito", "aws-inventory", "search-cluster" ]

def main(args):

    todo = []
    if args.stack != "all":
        if args.stack not in components:
            logger.critical(f"{args.stack} is not a valid component of Antiope")
            exit(1)
        else:
            todo = [args.stack]
    else:
        todo = components

    src_data = get_config(args.src)
    dst_data = get_config(args.dst)

    for stack_name in todo:
        src_lambda = get_lambda_package_key(src_data, args.src, stack_name)
        if src_lambda is None:
            print("aborting...")
            exit(1)
        logger.debug(f"src_lambda: {src_lambda}")

        copy_object(src_data['BUCKET'], dst_data['BUCKET'], src_lambda)

        template_key = src_lambda.replace("lambda", "Template").replace(".zip", ".yaml")
        logger.debug(f"template_key: {template_key}")

        copy_object(src_data['BUCKET'], dst_data['BUCKET'], template_key)

        manifest_file = f"{stack_name}/cloudformation/{src_data['STACK_PREFIX']}-{args.dst}-{stack_name}-Manifest.yaml"
        logger.debug(f"manifest_file: {manifest_file}")

        template_url = f"https://s3.amazonaws.com/{dst_data['BUCKET']}/{template_key}"

        command = f"deploy_stack.rb -m {manifest_file} --template-url {template_url} pLambdaZipFile={src_lambda} pBucketName={dst_data['BUCKET']} --force"
        logger.info(f"command: {command}")
        os.system(command)




def get_lambda_package_key(src, env, stack_name):
    cf_client = boto3.client('cloudformation', region_name=src['AWS_DEFAULT_REGION'])
    full_stack_name = f"{src['STACK_PREFIX']}-{env}-{stack_name}"
    response = cf_client.describe_stacks(StackName=full_stack_name)
    for p in response['Stacks'][0]['Parameters']:
        if p['ParameterKey'] == "pLambdaZipFile":
            return(p['ParameterValue'])
    logger.critical(f"Unable to file a pLambdaZipFile for {full_stack_name}")
    return(None)

def copy_object(src_bucket, dst_bucket, object_key):
    client = boto3.client('s3')
    try:
        logger.info(f"Copying {object_key} from {src_bucket} to {dst_bucket}")
        response = client.copy_object(
            ACL='private',
            Bucket=dst_bucket,
            ContentType='application/zip',
            CopySource={'Bucket': src_bucket, 'Key': object_key},
            Key=object_key,
        )
    except ClientError as e:
        logger.critical(f"Failed to copy {object_key} from {src_bucket} to {dst_bucket}")
        exit(1)


def get_config(environment):
    '''source an antiope makefile config for key variables'''

    output = {}

    filename = f"config.{environment}"
    if not os.path.isfile(filename):
        logger.critical(f"Cannot find config file {filename}. Aborting...")
        exit(1)

    with open(filename, "r") as file:
        data = file.readlines()
        for line in data:
            key,value = line.split("=")
            output[key] = value.replace("\n", "")

    return(output)





def do_args():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", help="print debugging info", action='store_true')
    parser.add_argument("--error", help="print error info only", action='store_true')

    # parser.add_argument("--env_file", help="Environment File to source", default="config.env")

    parser.add_argument("--src", help="Source Environment to Promote", required=True)
    parser.add_argument("--dst", help="Destination Environment", required=True)
    parser.add_argument("--stack", help="Antiope Component to promote", default="all")

    args = parser.parse_args()
    return(args)



if __name__ == '__main__':

    args = do_args()



    # Logging idea stolen from: https://docs.python.org/3/howto/logging.html#configuring-logging
    # create console handler and set level to debug
    ch = logging.StreamHandler()
    if args.debug is True:
        logger.setLevel(logging.DEBUG)
    elif args.error is True:
        logger.setLevel(logging.ERROR)
    else:
        logger.setLevel(logging.INFO)

    # create formatter
    # formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    # add formatter to ch
    ch.setFormatter(formatter)
    # add ch to logger
    logger.addHandler(ch)

    main(args)
    exit(0)
