#!/usr/bin/env python3
"""
awsevent object to recurse and extract a list of events from within an AWS event received from SNS or SQS
         can be extended to other types of events

         initialize with an event
         evt = awsevent(event)
         evt.events a sequential list of events { source: str, records: [] }
         typically your most interested in evt.events[-1]

         if an S3 event has been passed from SNS to SQS the events array produced by the object will contain the
         following sources "aws:sns", "aws:sqs", "aws:s3"
"""
import json

class AWSevent(dict):
    def __init__(self, event, **kwargs):
        self.source_keys = [ "EventSource", "eventSource" ]
        self.event_sources = [ "aws:sns", "aws:sqs", "aws:s3" ]
        self.carrier_sources = [ "sns", "sqs" ]
        self.event = event
        self.events = {}
        self.extract_events(event)

    def extract_events( self, event ):
        if "Records" in event:
            for record in event[ "Records" ]:
                src = self.extract_source( record )
                if src not in self.events:
                    self.events[src] = []
                content = getattr( self, src )
                evt = content(record)
                self.events[src].append( evt )
                if src in self.carrier_sources:
                    self.extract_events( evt )
        else:
            src = self.extract_source( event )
            if src is None:
                return
            if src not in self.events:
                self.events[src] = []
            content = getattr( self, src )
            evt = content(event)
            self.events[src].append( evt )
            if src in self.carrier_sources:
                self.extract_events( evt )

    def extract_source(self, record):
        for key in self.source_keys:
            if key in record:
                if record[ key ] in self.event_sources:
                    return( record[ key ].split(':')[1] )
        # AWS stripped the eventsource so we have guess
        if "TopicArn" in record:
            return( "sns" )
        
    def sns(self, record):
        if "Sns" in record:
            return( json.loads( record[ "Sns" ][ "Message" ] ) )
        if "Message" in record:
            return( json.loads( record[ "Message" ] ) )

    def sqs(self, record):
        return(  json.loads( record[ "body" ] ) )

    def s3(self, record):
        return( record )

if __name__ == '__main__':
    from resourceloader import resourceloader
    import sys
    event = json.loads( resourceloader( src=f'file://{sys.argv[1]}' ).getdata() )
    #event = json.loads( resourceloader( src="file://../../etc/s3toSQSResources2Events.json" ).getdata() )
    #event = json.loads( resourceloader( src="file://../../../wmcso-pylib/etc/sqs_deadletter.json" ).getdata() )
    evt = AWSevent(event)

    # the events attribute is what your interested in and typically the last event
    # the records element of the object are the raw records for that event
    #print( f'{evt.events[-1]["records"][0]["s3"]["bucket"]["name"]}' )

    print( json.dumps( evt.events, indent=2 ) )
    if "s3" in evt.events:
        print( "found s3")
    for key in evt.events:
        print( f"{key} has {len( evt.events[key] ) } events" )

    # iterate all return
    # for e in evt.events:
    #     print( f'source = {e["source"]}' )
    #     if e["source"] == "aws:s3":
    #         print( f'Records = {e["records"]}')
    #         for r in e["records"]:
    #             print( r["s3"]["bucket"]["name"])
