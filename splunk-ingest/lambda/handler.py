#!/usr/bin/env python3
"""
    waf_log_to_splunk.py:  Triggered by SNS topic attached to S3 bucket where AWS Inspector FINDING_REPORTED events
                            are saved by finding-reported lambda.  Writes finding to Splunk index.  Token and secret
                            are stored in secrets manager.
"""
import boto3
import json
import os
import logging
import gzip
from urllib.parse import unquote
from botocore.exceptions import ClientError

from resourceloader import resourceloader
from awssecret import get_secret
from splunkhec import SplunkHEC
from awsevents import AWSevent

logger = logging.getLogger()
for name in logging.Logger.manager.loggerDict.keys():
    if ('boto' in name) or ('urllib3' in name) or ('s3transfer' in name) or ('boto3' in name) or ('botocore' in name) or ('nose' in name):
        logging.getLogger(name).setLevel(logging.WARNING)
logger.setLevel(getattr(logging, os.getenv('LOG_LEVEL', default='INFO')))
logging.basicConfig()

# we only want to retrieve these once
hec_token = get_secret( os.environ["HecAccessTokenSecretArn"] )[ "HecAccessToken" ]


def handler( event, context ):

    # manipulate logging messages in the lambda env so we get a run id on every message
    if os.getenv( 'AWS_EXECUTION_ENV' ):
        ch = logging.StreamHandler()
        formatter = logging.Formatter(f'{context.aws_request_id} [%(levelname)s] %(message)s')
        ch.setFormatter(formatter)
        logger.handlers = []
        logger.addHandler(ch)

    # put the event out in the logs
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))

    # we're only interested in the s3 events
    evt = AWSevent( event )

    # list the event chain since we also service a dead letter queue events can be wrapped
    logger.debug( f'Events types found:{ [ e for e in evt.events ] }')

    # the last event in the list the one we are interested in
    if "s3" not in evt.events:
        logger.info( f'No s3 records found within event: {event}')
        return( event )

    # allocate the Splunk hec object
    hec = SplunkHEC( os.environ["SplunkHecUrl"], hec_token )

    for record in evt.events["s3"]:

        # this lambda reacts to the message within the SQS message so lets say what that is.
        logger.debug( "Event Message:" + json.dumps(record, sort_keys=True) )

        # establish object to read
        s3Object = f's3://{record["s3"]["bucket"]["name"]}/{unquote( record["s3"]["object"]["key"] ).replace( "+", " ")}'

        # load the object from s3
        logger.debug( f'loading object: {s3Object}')
        resource = resourceloader( src=s3Object, ).getdata().decode("utf-8")

        # set the meta data
        hec.set_metadata(index=os.environ["SplunkIndex"], host=s3Object, sourcetype="json")

        # push resource to Splunk discarding the data if we get a 503 because it is too big
        status, text = hec.batch_events( resource )
        if status != 200:
            logger.error( f'{status}, {text}')
            if status != 503:
                raise Exception( f'Splunk returned {status}, {text}' )
            else:
                return( event )


# flush out the buffer discarding the data if we get a 503 because it is too big
    status, text = hec.send()
    if status != 200:
        logger.error( f'{status}, {text}')
        if status != 503:
            raise Exception( f'Splunk returned {status}, {text}' )
    else:
        logger.debug( f'Splunk returned {status}, {text}' )


    return( event )
