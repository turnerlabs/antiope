# Copyright 2021 Chris Farris <chrisf@primeharbor.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import boto3
from botocore.exceptions import ClientError
import json
import os
import time
from datetime import datetime, timezone
from dateutil import tz

from antiope.aws_account import *
from common import *

import logging
logger = logging.getLogger()
logger.setLevel(getattr(logging, os.getenv('LOG_LEVEL', default='INFO')))
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

RESOURCE_PATH = "organizations/account"
CONTACT_TYPES= ['BILLING', 'OPERATIONS', 'SECURITY']
assume_role_url = "https://signin.aws.amazon.com/switchrole?account={}&roleName={}&displayName={}"

def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])

        # Shield Advanced is a global thing with a single subscription per account
        client = target_account.get_client('account')
        ec2_client = target_account.get_client('ec2')

        resource_item = {}
        resource_item['awsAccountId']                   = target_account.account_id
        resource_item['awsAccountName']                 = target_account.account_name
        resource_item['resourceType']                   = "AWS::Organizations::Account"
        resource_item['source']                         = "Antiope"
        resource_item['ARN']                            = target_account.db_record['payer_record']['Arn']
        resource_item['resourceCreationTime']           = target_account.db_record['payer_record']['JoinedTimestamp']
        resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
        resource_item['configuration']                  = target_account.db_record.copy()   # This is non-standard, 'configuration' is usually only the
                                                                                            # return of the describe or list call. In this case it is a
                                                                                            # full dump of the ddb record
        resource_item['supplementaryConfiguration']     = {}
        resource_item['resourceId']                     = target_account.account_id
        resource_item['resourceName']                   = target_account.account_name
        resource_item['errors']                         = {}

        if hasattr(target_account, 'cross_account_role') and target_account.cross_account_role is not None:
            role_name = target_account.cross_account_role.split("/")[-1]
            resource_item['supplementaryConfiguration']['assume_role_url'] = assume_role_url.format(target_account.account_id, role_name, target_account.account_name)



        contact_ddb_attrib = {}
        for contact_type in CONTACT_TYPES:
            try:
                contact = client.get_alternate_contact(AlternateContactType=contact_type)
                del contact['ResponseMetadata']
                resource_item['supplementaryConfiguration'][f"AlternateContact-{contact_type}"] = contact['AlternateContact']
                contact_ddb_attrib[contact_type] = contact
            except ClientError as e:
                if e.response['Error']['Code'] == 'AccessDeniedException':
                    logger.error(f"Antiope doesn't have proper permissions to this account or permission to the AccountAPI: {e}")
                    resource_item['errors']['AlternateContacts'] = f"Antiope doesn't have proper permissions to this account or permission to the AccountAPI: {e}"
                    pass
                elif e.response['Error']['Code'] == 'ResourceNotFoundException':
                    logger.error(f"{message['account_id']} doesn't have an AlternateContact of type {contact_type}")
                    resource_item['errors'][f"AlternateContacts-{contact_type}"] = f"{message['account_id']} doesn't have an AlternateContact of type {contact_type}"
                else:
                    raise
        target_account.update_attribute("AlternateContacts", contact_ddb_attrib)

        # Gather what regions are enabled
        resource_item['supplementaryConfiguration']['Regions'] = {} # structure this array into a dict for cleaner json
        all_regions = ec2_client.describe_regions(AllRegions=True)['Regions']
        for r in all_regions:
            resource_item['supplementaryConfiguration']['Regions'][r['RegionName']] = r

        # Iterate the regions to find weird Wavelength and LocalZones that might be enabled
        zones = {}
        zone_errors = {}
        enabled_regions = target_account.get_regions()  # we can only ask about AZs in enabled regions
        for r in enabled_regions:
            try:
                regional_client = target_account.get_client("ec2", region=r)
                regional_zones = regional_client.describe_availability_zones(AllAvailabilityZones=True)['AvailabilityZones']
                zones[r] = {} # structure this array into a dict for cleaner json
                for z in regional_zones:
                    zones[r][z['ZoneName']] = z
            except ClientError as e:
                # If the antiope account isn't enabled for the region, then it can't do the cross-account AssumeRole.
                if e.response['Error']['Code'] == 'UnauthorizedOperation':
                    zone_errors[r] = f"Antiope doesn't have proper permissions to region {r} in account ({message['account_id']}): {e}"
                    logger.error(zone_errors[r])

        resource_item['supplementaryConfiguration']['AvailabilityZones'] = zones
        if zone_errors != {}:
            resource_item['errors']['AvailabilityZones'] = zone_errors

        save_resource_to_s3(RESOURCE_PATH, f"{target_account.account_id}", resource_item)

    except AntiopeAssumeRoleError as e:
        logger.error("Unable to assume role into account {}({})".format(target_account.account_name, target_account.account_id))
        return()
    except ClientError as e:
        if e.response['Error']['Code'] == 'UnauthorizedOperation':
            logger.error(f"Antiope doesn't have proper permissions to account ({message['account_id']}): {e}")
            return(event)
        logger.critical("AWS Error getting info for {}: {}".format(message['account_id'], e))
        capture_error(message, context, e, "ClientError for {}: {}".format(message['account_id'], e))
        raise
    except Exception as e:
        logger.critical("{}\nMessage: {}\nContext: {}".format(e, message, vars(context)))
        capture_error(message, context, e, "General Exception for {}: {}".format(message['account_id'], e))
        raise
