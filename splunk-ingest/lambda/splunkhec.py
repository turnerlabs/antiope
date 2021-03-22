#!/usr/bin/env python3
"""
Sends Json data to Splunk
Example use:
hec = SplunkHEC( "https://splunk.mydomain.com", hec_token )
           status, text = hec.send( obj, metadata={ "index": "myindex" } )
           if status != 200:
               print( f'{status}, {text}')
           else:
               sent_ctr += 1
"""

import urllib3
import certifi
import json

class SplunkHEC:

    def __init__(self, uri, token, port='8088'):
        if not 'http' in uri:
            return(None)
        self.token = token
        self.host = uri.replace( "https://", '', 1)
        self.uri = uri+":"+port+"/services/collector/event"
        self.port = port
        self.maxmsgsize = 512000
        self.metadata = {}
        self.batch_init()

    def set_metadata(self, **kwargs):
        for key, val in kwargs.items():
            self.metadata[key] = val

    # sallow calling program to reset counters as desired.
    def batch_init(self):
        self.eventssent = 0
        self.events = []
        self.eventslen = 0

    def batch_events( self, event ):
        # combine the metadata with the event passed in to produce a payload
        payload = self.metadata.copy()
        payload.update( { "event": event } )

        # convert the payload to a string
        eventstr = json.dumps( payload, default=str )
        eventlen = len( eventstr )

        # append if less than max.  send if makes collected events > max
        if ( self.eventslen + eventlen + len( self.events ) ) < self.maxmsgsize:
            self.events.append( eventstr )
            self.eventslen += eventlen
            return( 200, "Success" )
        else:
            if len( self.events ) > 0:
                status, text = self.send()
                if status == 200:
                    self.events.append( eventstr )
                    self.eventslen += eventlen
                return( status, text )
            if eventlen < self.maxmsgsize:
                self.events.append( eventstr )
                self.eventslen += eventlen
                return( 200, "Success")
            else:
                return 503, f"Event data len {eventlen} exceeds maximum of {self.maxmsgsize}."


    """
    event data is the actual event data
    metadata are sourcetype, index, etc
    """
    def send(self, event=None, metadata=None):
        http_headers = {'Authorization': 'Splunk '+ self.token}
        http_body = " ".join( self.events )

        if len( http_body ) > self.maxmsgsize:
            return 503, f"Event data len {len(http_body)} exceeds maximum of {self.maxmsgsize}."

        http = urllib3.PoolManager(ca_certs=certifi.where())

        r = http.request('POST', self.uri, headers=http_headers, body=http_body)

        if r.status == 200:
            self.eventssent += len( self.events )
            self.events = []
            self.eventslen = 0

        return r.status, r.data,