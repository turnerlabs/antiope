import re
from pprint import pprint
import boto3
from botocore.exceptions import ClientError

class resourceloader(dict):
    def __init__(self, src=None, **kwargs):
        
        # add necessary properties to class
        self.setproperty( "src", src )
        
        # set any defaults
        self.verbosity = False

        # apply overrides given at initialization
        for kwarg in kwargs:
            self.setproperty( kwarg, kwargs[kwarg] )

        # set supported protocols
        protocols = {
                "file": self.load_from_disk,
                "s3": self.load_from_bucket,
                "ddb": self.load_from_ddb_table
                }
        
        # iterate protocols and execute respective loader
        for key in protocols.keys():
            proto = f'{key}://'
            if src.startswith( proto ):
                self.setproperty( "path", self.src.replace( proto, '', 1 ) )
                if self.verbosity:
                    print( f'Loading: {self.src}')
                protocols[key]()
        
        
    def load_from_disk( self ):
        try:
            with open(self.path) as fd:
                self.setproperty( 'data', fd.read() )
        except Exception as e:
            print( f'{e} src={self.src}' )
            raise( e )


    def load_from_bucket(self):
        client = boto3.client('s3')
        try:
            bucket = re.split( '/', self.path, 1 )[0]
            key = re.split( '/', self.path, 1)[1]
            response = client.get_object(
                Bucket=bucket,
                Key=key
            )
            self.setproperty( 'data', response['Body'].read() )
            
        except ClientError as e:
            print( f'{e} src={self.src}' )
            raise(e)

    def load_from_ddb_table(self):
        ddb = boto3.resource('dynamodb')
        try:
            table = ddb.Table(self.path)
            response = table.scan()  #leaving this here for future when ddbs grow beyond 1meg
            data = []
            self.setproperty( 'data', data )
            while True:
                self.data.extend( response[ "Items" ] )
                if "LastEvaluatedKey" in response:
                    response = table.scan( ExclusiveStartKey=response['LastEvaluatedKey'], )
                else:
                    break

        except ClientError as e:
            print( f'{e} src={self.src}' )
            raise(e)
            
    def setproperty( self, key, val ):
        setattr( self, key, val )
        self[key] = val
    
    def getdata(self):
        return( self.data )