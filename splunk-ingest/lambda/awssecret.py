#!/usr/bin/env python3

import boto3
import json
import os
import base64
from botocore.exceptions import ClientError

def get_secret(secret_name, region=os.environ['AWS_DEFAULT_REGION']):
    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region)

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        print(f"Client error {e} getting secret")
        raise e
    else:
        if 'SecretString' in get_secret_value_response:
            secret = get_secret_value_response['SecretString']
            return json.loads(secret)
        else:
            decoded_binary_secret = base64.b64decode(get_secret_value_response['SecretBinary'])
            return(decoded_binary_secret)
    return None