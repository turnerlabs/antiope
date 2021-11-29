#!/usr/bin/env python3
"""
    handler.py:  Triggered by SNS topic attached to S3 bucket where an s3 create events are sent.
                            
"""
import json
import os
import logging
import hashlib
from urllib.parse import unquote
from botocore.exceptions import ClientError


from resourceloader import resourceloader
from awssecret import get_secret
from awselasticsearch import AwsElasticSearch
from awsevents import AWSevent

logger = logging.getLogger()
for name in logging.Logger.manager.loggerDict.keys():
    if ('boto' in name) or ('urllib3' in name) or ('s3transfer' in name) or ('boto3' in name) or ('botocore' in name) or ('nose' in name) or ('elasticsearch' in name):
        logging.getLogger(name).setLevel(logging.WARNING)
logger.setLevel(getattr(logging, os.getenv('LOG_LEVEL', default='INFO')))
logging.basicConfig()

# antiope's index model queries AWS for resources and writes each resource as an object in s3
# the prefix to this object is used to define the name of the Elastic Search index and the object is
# then inserted into Elastic Search. The array below excludes insertion from the specified prefix.
excluded_resource_prefixes=[]
if 'EXCLUDED_RESOURCE_PREFIXES' in os.environ:
    if os.environ['EXCLUDED_RESOURCE_PREFIXES'] != '':
        excluded_resource_prefixes=os.environ['EXCLUDED_RESOURCE_PREFIXES'].split(',')


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

    es = AwsElasticSearch( endpoint=f'https://{os.getenv("ES_DOMAIN_ENDPOINT")}' )
    all_es_indexes = es.ListIndexes().keys()
    
    for record in evt.events["s3"]:

        # this lambda reacts to the message within the SQS message so lets say what that is.
        logger.debug( "Event Message:" + json.dumps(record, sort_keys=True) )

        if prefix_excluded( record["s3"]["object"]["key"] ):
            logger.warning( f'Prefix {record["s3"]["object"]["key"]} excluded: skipping insertion into ES' )
            continue

        # establish object to read
        s3Object = f's3://{record["s3"]["bucket"]["name"]}/{unquote( record["s3"]["object"]["key"] ).replace( "+", " ")}'

        # load the object from s3
        logger.info( f'loading object: {s3Object}')
        res_as_string = resourceloader( src=s3Object, ).getdata().decode("utf-8")
        res_as_string = fix_principal(res_as_string)

        # This is a shitty hack to get around the fact Principal can be "*" or {"AWS": "*"} in an IAM Statement
        resource = json.loads( res_as_string )

        # Time is required to have '.' and 6 digits of precision following.  Some items lack the precision so add it.
        if "configurationItemCaptureTime" in resource:
            if '.' not in resource[ "configurationItemCaptureTime"]:
                resource[ "configurationItemCaptureTime" ] += ".000000"

        # break the key into parts
        key_parts = record["s3"]["object"]["key"].lower().replace( ".json", "").split("/")

        # make a doc id we do it different 
        if key_parts[0].startswith( "azure" ):
            id = str(resource['configuration']['id']).strip('"').replace("/","_").replace("_","",1)
            doc_id = hashlib.md5(id.encode()).hexdigest()
            index = "_".join(key_parts[:-1])
        else: # its aws
            doc_id = key_parts.pop().replace(".json", "")
            index = "_".join(key_parts)
        
        if index not in all_es_indexes:
            if "azure" in index:
                mkAzureResourceIndex(es.es, index)
            else:
                logger.debug( f'S3 key produced unknown index  = {index}, s3key =  {record["s3"]["object"]["key"]}')
        try:
            es.es.index(index=index, id=doc_id, document=resource)
        except Exception as e:
            logger.error(f'Failed to insert object from {s3Object} {e}')
            

    return( event )

def prefix_excluded(s3key):
    for prefix in excluded_resource_prefixes:
        if s3key.startswith( prefix ):
            return True
    return False

def mkAzureResourceIndex(es, index):
    es.indices.create( index=index, mappings={ "_doc": {
                                                        "properties":{
                                                            "configurationItemCaptureTime": {
                                                            "format": "yyyy-MM-dd HH:mm:ss.SSSSSS",
                                                            "type": "date"
                                                            }
                                                        }
                                                    }
                                                })
    es.index(index=".kibana", doc_type="doc", id=f"index-pattern:{index}", document={
                                                                                        "index-pattern": {
                                                                                            "title": index,
                                                                                            "timeFieldName": "configurationItemCaptureTime"
                                                                                        },
                                                                                        "type": "index-pattern"
                                                                                        })

def fix_principal(json_doc):
    """
    WTF are we doing here? Good Question!
    ElasticSearch has an oddity where it can't handle a attribute being a literal or another level of nesting. This becomes and issue when the "Principal" in a statement
    can be one of:
        "Principal": "*" ; or
        "Principal": { "AWS": "*" } ; or
        "Principal": { "Service": "someservice.amazonaws.com" }

    You end up with an error for the first condition that states:
        'type': 'mapper_parsing_exception',
        'reason': 'object mapping for [supplementaryConfiguration.Policy.Statement.Principal] tried to parse field [Principal] as object, but found a concrete value'

    What this function will do is a total hack. It will modify the "Principal": "*" case to be "Principal": { "ALL": "*" }
    That will permit the document to be indexed and offers some level of indication as to what is happening. I hate it, but it's the best idea I've got right now.

    Note: I believe that there is a distinction between Principal: * and Principal: AWS: * - the former indicates no AWS auth is occuring at all , whereas the AWS: * means any AWS Customer (having previously authenticated to their own account). Both are bad.
    """

    
    

    # Convert to String, Make sure there are no spaces between json elements (so it can match with string_to_match)
    # json_string = json.dumps(json_doc, separators=(',', ':'), indent=None)

    # print(f"In fix principal, json_string is {json_string}")

    # Do the replace
    string_to_sub = '"Principal": { "ALL": "*" }'
    json_doc = json_doc.replace('"Principal":"*"', string_to_sub)
    json_doc = json_doc.replace('"Principal": "*"', string_to_sub)
    return( json_doc )

    # # Convert back to dict
    # modified_json_doc = json.loads(modified_json_string)

    # return(modified_json_doc)