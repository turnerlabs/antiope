#!/usr/bin/env python3
"""
awselasticsearch.py class for working with AWS Enhanced ElasticSearch.
"""
import os
import boto3
from requests_aws4auth import AWS4Auth
from elasticsearch import Elasticsearch, RequestsHttpConnection
from urllib.parse import urlparse

class AwsElasticSearch(dict):
    def __init__(self, opts=None, **kwargs):
        # set defaults.
        self.opts = {}
        self.opts["use_ssl"] = True
        self.opts["port"] = 443
        self.opts["use_ssl"] = True
        self.opts["verify_certs"] = True
        self.opts["connection_class"]=RequestsHttpConnection
        self.opts["scroll"] = '2m'
        self.opts["headers"] = {"Content-Type": "application/json"}
        # set overrides
        if opts is not None:
            for key in opts:
                if key == "creds":
                    self.opts[ "auth" ] = (opts.creds["key"], opts.creds["secret"])
                else:
                    self.opts[key]=opts[key]
        for key in kwargs:
            if key == "creds":
                self.opts[ "auth" ] = (kwargs["creds"]["key"], kwargs["creds"]["secret"])
            else:
                self.opts[key]=kwargs[key]

        # if no creds provided pull from env
        if "creds" not in self.opts:
            self.extract_credentials_from_env()
    
        # if an endping was given extract the port, host and protocol 
        if "endpoint" in self.opts:
            o = urlparse( self.opts["endpoint"])
            self.opts["host"] = o.hostname
            if o.scheme == "http":
                self.opts["port"] = 80
            if "port" in o:
                self.opts["port"] = o.port
            
        # establish the connection to elastic search
        self.es = Elasticsearch(
                hosts = [{'host': self.opts["host"], 'port': self.opts["port"]}],
                http_auth=self.opts["creds"],
                use_ssl=self.opts["use_ssl"],
                verify_certs=self.opts["verify_certs"],
                connection_class=self.opts["connection_class"]
            )
    
    def extract_credentials_from_env(self):
        credentials = boto3.Session().get_credentials()
        self.opts["creds"] = AWS4Auth(
                credentials.access_key,
                credentials.secret_key,
                os.getenv("AWS_DEFAULT_REGION"),
                "es",
                session_token=credentials.token)

    def ExtractRecords(self, index=None, query=None):
        if index is not None:
            self.opts["index"] = index
        if query is not None:
            self.opts["query"] = query 

        output = []

        if hasattr(self, 'scroll_id'):
            res = self.es.scroll(scroll_id = self.scroll_id, scroll = self.opts["scroll"])
            if len(res['hits']['hits']) == 0:
                return(None)
            self.scroll_id = res['_scroll_id']
            self.scroll_size = res['hits']['total']
            for hit in res['hits']['hits']:
                hit['_source']['_id'] = hit['_id']  # Make sure we always have a unique identifier
                output.append(hit["_source"])

        else:
            # perform the initial query
            res = self.es.search(index=self.opts["index"], body=self.opts["query"], scroll=self.opts["scroll"])
            self.scroll_id = res['_scroll_id']
            self.scroll_size = res['hits']['total']
            for hit in res['hits']['hits']:
                hit['_source']['_id'] = hit['_id']  # Make sure we always have a unique identifier
                output.append(hit["_source"])

        return(output)

    def Insert(self, body, opts=None):

        self.es.bulk(body, index=self.opts["index"], headers=self.opts["headers"])

    def ListIndexes(self):
        return(self.es.indices.get_alias("*"))

if __name__ == '__main__':
    import json
    es = AwsElasticSearch( endpoint = "https://search-warnermedia-antiope-dev-l265jyfmwqagp2fjkopcx6z7pe.us-east-1.es.amazonaws.com")
    #es = AwsElasticSearch( endpoint="https://search-warnermedia-antiope-prod2-3mmmneoc5yyomlndz4dwtud4ru.us-east-1.es.amazonaws.com" )

    
    #print( f'{es.ListIndexes()}')

    last24h = {
            "size": 5000,
            "query": {"range" : {"configurationItemCaptureTime" : {"gte" : "now-24h"} } }
            }
    match_all = {
        "size": 5000,
        "query": {"match_all" : {} }
        }

    #items = es.ExtractRecords( "resources_wafv2_webacl", last24h )
    items = es.ExtractRecords( "astra_cloudinspect_v1", match_all )
    #items = es.ExtractRecords( "resources_ec2_instance", last24h )
    while items is not None:
        for item in items:
            print( json.dumps( item, indent=2))
        items = es.ExtractRecords()
        
    #es.Insert( "david_hamm", )