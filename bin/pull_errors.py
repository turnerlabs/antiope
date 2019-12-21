#!/usr/bin/env python3

## Script to pull events off the error queue for inspection

import boto3
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

header_row = "<tr><td>Function Name</td><td>Error Time</td><td>Error Message</td><td>Function Logs</td>"

def main(args, logger):
    sqs_client = boto3.client('sqs')

    queue_url = get_queue_url(args.queue_name)

    region = os.environ['AWS_DEFAULT_REGION']

    table_data = ""
    count = 0

    response = sqs_client.receive_message(
        QueueUrl=queue_url,
        AttributeNames=['All'],
        MaxNumberOfMessages=10,
        VisibilityTimeout=10,
        WaitTimeSeconds=10,
    )

    try:
        while 'Messages' in response and len(response['Messages']) > 0:

            for m in response['Messages']:
                # print messages
                print(m['MessageId'])
                sent_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(m['Attributes']['SentTimestamp'])/1000))
                error_string = format_error(m['Body'], region, sent_time)
                # print(error_string)
                table_data += error_string
                count += 1

                # # delete messages
                # print(f"Deleting {m['ReceiptHandle']}")
                if args.delete:
                    sqs_client.delete_message(QueueUrl=queue_url, ReceiptHandle=m['ReceiptHandle'])

            # get more
            response = sqs_client.receive_message(
                QueueUrl=queue_url,
                AttributeNames=['All'],
                MaxNumberOfMessages=10,
                VisibilityTimeout=30,
                WaitTimeSeconds=5,
            )
        write_file(table_data, args, count)
    except KeyboardInterrupt:
        write_file(table_data, args, count)


def write_file(table_data, args, count):
    f = open(args.filename,"w+")
    f.write(f"<html><head><title>Output Report for {args.queue_name}</title></head>")
    f.write(f"<body><h1>Output Report for {args.queue_name}</h1>")
    f.write(f"<table border=1>{header_row}")
    f.write(table_data)
    f.write("</table>")
    f.write(f"Total Errors: {count}</body></html>")
    f.close()



## End ##
def format_error(error_raw, region, sent_time):
    error_json = json.loads(error_raw)
    error_url = f"https://console.aws.amazon.com/cloudwatch/home?region={region}#logEventViewer:group={error_json['log_group_name']};stream={error_json['log_stream_name']}"

    output = f"<tr><td>{error_json['function_name']}</td>\n"
    output += f"<td>{sent_time}</td>\n"
    output += f"<td>{error_json['message']}</td>\n"
    output += f"<td><a href='{error_url}'>CloudWatch Logs</a></td></tr>\n"

    return(output)


def get_queue_url(queue_name):
    try:
        sqs_client = boto3.client('sqs')
        response = sqs_client.get_queue_url(
            QueueName=queue_name,
        )
        if 'QueueUrl' in response:
            return(response['QueueUrl'])
        else:
            return(None)
    except ClientError as e:
        print(f"Fatal error getting QueueUrl: {e}")
        exit(1)


def do_args():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", help="print debugging info", action='store_true')
    parser.add_argument("--error", help="print error info only", action='store_true')

    parser.add_argument("--queue_name", help="Name of Queue to dump", required=True)
    parser.add_argument("--filename", help="Filename for HTML Report", required=True)
    parser.add_argument("--delete", help="Delete the messages after printing them", action='store_true')

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

    # # Sanity check region
    # if args.region:
    #     os.environ['AWS_DEFAULT_REGION'] = args.region

    # if 'AWS_DEFAULT_REGION' not in os.environ:
    #     logger.error("AWS_DEFAULT_REGION Not set. Aborting...")
    #     exit(1)

    try:
        main(args, logger)
    except KeyboardInterrupt:
        exit(1)