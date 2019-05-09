#!/usr/bin/env python3

import boto3
from botocore.exceptions import ClientError
import os
import sys
import json
from pprint import pprint
import os.path
import time
from datetime import tzinfo


try:
    from cftdeploy.stack import *
    from cftdeploy.manifest import *
except ImportError as e:
    print("Must install python module cftdeploy")
    print("Error: {}".format(e))
    exit(1)

import logging
logger = logging.getLogger()
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)


def main(args):

    src_data = get_config(args.src)
    dst_data = get_config(args.dst)
    src_stack_name = f"{src_data['STACK_PREFIX']}-{args.src}-{args.stack}"
    dest_stack_name = f"{dst_data['STACK_PREFIX']}-{args.dst}-{args.stack}"

    try:
        my_source_stack = CFStack(src_stack_name, src_data['AWS_DEFAULT_REGION'])
    except CFStackDoesNotExistError as e:
        print(f"Cannot find source stack: {src_stack_name} in {src_data['AWS_DEFAULT_REGION']}. Aborting...")
        exit(1)

    src_stack_outputs = my_source_stack.get_outputs()
    version = src_stack_outputs['Version']

    # These are what the makefile uses
    dest_stack_params = {
        'pBucketName': dst_data['BUCKET'],
        'pVersion': version
    }

    # Only copy the Lambda package if it is part of the template
    if 'LambdaPackageFile' in src_stack_outputs:
        lambda_key = src_stack_outputs['LambdaPackageFile']
        logger.debug(f"lambda_key: {lambda_key}")
        copy_object(src_data['BUCKET'], dst_data['BUCKET'], lambda_key)
        dest_stack_params['pLambdaZipFile'] = lambda_key


    # Pull down the Template from the current stack....
    src_template = my_source_stack.get_template()

    # And save it back to the destination bucket
    dest_template_key = f"deploy-packages/{dest_stack_name}-Template-{version}.yaml"
    src_template.upload(dst_data['BUCKET'], dest_template_key)

    # Determine the manifest file and set it up
    try:
        manifest_file = f"{args.stack}/cloudformation/{dest_stack_name}-Manifest.yaml"
        if args.path:
            manifest_file = args.path + "/" + manifest_file

        logger.debug(f"manifest_file: {manifest_file}")
        my_manifest = CFManifest(manifest_file, region=dst_data['AWS_DEFAULT_REGION'])
        my_manifest.override_option("S3Template", f"https://s3.amazonaws.com/{dst_data['BUCKET']}/{dest_template_key}")
    except Exception as e:
        logger.critical(f"Unspecified error prepping the manifest: {e}. Aborting....")
        exit(1)


    print(f"Promoting {version} from {src_stack_name} to {dest_stack_name} with manifest_file {manifest_file}")

    # Now see if the stack exists, if it doesn't then create, otherwise update
    try:
        my_dest_stack = CFStack(dest_stack_name, dst_data['AWS_DEFAULT_REGION'])

        # Only if the stack is in a normal status (or --force is specified) do we update
        status = my_dest_stack.get_status()
        if status not in StackGoodStatus and args.force is not True:
            print(f"Stack {my_dest_stack.stack_name} is in status {status} and --force was not specified. Aborting....")
            exit(1)

        rc = my_dest_stack.update(my_manifest, override=dest_stack_params)
        if rc is None:
            print("Failed to Find or Update stack. Aborting....")
            exit(1)
    except CFStackDoesNotExistError as e:
        logger.info(e)
        # Then we're creating the stack
        my_dest_stack = my_manifest.create_stack(override=dest_stack_params)
        if my_dest_stack is None:
            print("Failed to Create stack. Aborting....")
            exit(1)

    # Now display the events
    events = my_dest_stack.get_stack_events()
    last_event = print_events(events, None)
    while my_dest_stack.get_status() in StackTempStatus:
        time.sleep(5)
        events = my_dest_stack.get_stack_events(last_event_id=last_event)
        last_event = print_events(events, last_event)

    # Finish up with an status message and the appropriate exit code
    status = my_dest_stack.get_status()
    if status in StackGoodStatus:
        print(f"{my_manifest.stack_name} successfully deployed: \033[92m{status}\033[0m")
        exit(0)
    else:
        print(f"{my_manifest.stack_name} failed deployment: \033[91m{status}\033[0m")
        exit(1)

def print_events(events, last_event):
    # Events is structured as such:
    # [
    #     {
    #         'StackId': 'arn:aws:cloudformation:ap-southeast-1:123456789012:stack/CHANGEME1/87b04ec0-5a46-11e9-b6d5-0200beb62082',
    #         'EventId': '87b11210-5a46-11e9-b6d5-0200beb62082',
    #         'StackName': 'CHANGEME1',
    #         'LogicalResourceId': 'CHANGEME1',
    #         'PhysicalResourceId': 'arn:aws:cloudformation:ap-southeast-1:123456789012:stack/CHANGEME1/87b04ec0-5a46-11e9-b6d5-0200beb62082',
    #         'ResourceType': 'AWS::CloudFormation::Stack',
    #         'Timestamp': datetime.datetime(2019, 4, 8, 21, 37, 38, 284000, tzinfo=tzutc()),
    #         'ResourceStatus': 'CREATE_IN_PROGRESS',
    #         'ResourceStatusReason': 'User Initiated'
    #     }
    # ]
    if len(events) == 0:
        return(last_event)
    for e in events:
        # Colors!
        if e['ResourceStatus'] in ResourceTempStatus:
            status = f"\033[93m{e['ResourceStatus']}\033[0m"
        elif e['ResourceStatus'] in ResourceBadStatus:
            status = f"\033[91m{e['ResourceStatus']}\033[0m"
        elif e['ResourceStatus'] in ResourceGoodStatus:
            status = f"\033[92m{e['ResourceStatus']}\033[0m"
        else:
            status = e['ResourceStatus']

        if 'ResourceStatusReason' in e and e['ResourceStatusReason'] != "":
            reason = f": {e['ResourceStatusReason']}"
        else:
            reason = ""
        print(f"{e['Timestamp'].astimezone().strftime('%Y-%m-%d %H:%M:%S')} {e['LogicalResourceId']} ({e['ResourceType']}): {status} {reason}")
    return(e['EventId'])

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
    parser.add_argument("--force", help="Force the stack update even if the stack is in a non-normal state", action='store_true')
    parser.add_argument("--src", help="Source Environment to Promote", required=True)
    parser.add_argument("--dst", help="Destination Environment", required=True)
    parser.add_argument("--stack", help="Antiope Component to promote", required=True)
    parser.add_argument("--path", help="Manifest Path (if not relative to this script)")

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
