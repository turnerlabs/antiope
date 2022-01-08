#!/bin/bash
# Copyright 2019-2020 Turner Broadcasting Inc. / WarnerMedia
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

if [ -z $MAIN_STACK_NAME ] ; then
  echo "MAIN_STACK_NAME is not in the environment, is this being executed from makefile or with env config.ENV"
  exit 1
fi

if [ -z $AWS_DEFAULT_REGION ] ; then
  echo "AWS_DEFAULT_REGION is not in the environment, is this being executed from makefile or with env config.ENV"
  exit 1
fi


# This is a definition of all the Resource Indcies that are created in ElasticSearch for AWS.
# Each Index needs to have a mapping defined before any indexing occurs
# Stylistically, indicies should be singular
# An index is defined based on the S3 path the object is found in. "resouces_$service_$resourceType"
INDICES="	resources_accessanalyzer_analyzer
			resources_accessanalyzer_finding
			resources_backup_backupvault
			resources_cloudformation_stack
			resources_cloudfront_distribution
			resources_cloudtrail_trail
			resources_cloudwatch_alarm
			resources_dx_connection
			resources_dx_gw
			resources_dx_vif
			resources_ec2_ami
			resources_ec2_clientvpn
			resources_ec2_eni
			resources_ec2_instance
			resources_ec2_securitygroup
			resources_ec2_snapshot
			resources_ec2_transitgateway
			resources_ec2_volume
			resources_ec2_vpc
			resources_ecr_repository
			resources_ecs_cluster
			resources_ecs_task
			resources_elb_loadbalancer
			resources_elbv2_loadbalancer
			resources_es_domain
			resources_guardduty_detector
			resources_iam_role
			resources_iam_saml
			resources_iam_user
			resources_kms_key
			resources_lambda_function
			resources_lambda_layer
			resources_rds_dbcluster
			resources_rds_dbinstance
			resources_redshift_clusters
			resources_route53_domain
			resources_route53_hostedzone
			resources_s3_bucket
			resources_sagemaker_notebook
			resources_secretsmanager_secret
			resources_shield_attack
			resources_shield_protection
			resources_shield_subscription
			resources_ssm_managedinstance
			resources_support_case
			resources_support_trustedadvisorcheckresult
			resources_wafv2_webacl
			resources_worklink_fleet"

# What does this script need to do:
# 	1. Enable the S3 Event on the Resources prefix of the S3 Bucket
# 	2. Enable S3 events on the azure/gcp stuff (someday)
# 	3. Enable Kibana Auth to the cluster
# 	3. Create the default index mapping for AWS resources
# 	4. Create the customized index mappins from the mappings directory

#
# Get some vars we'll need later
#
export SEARCH_STACK_NAME=`aws cloudformation describe-stacks --stack-name $MAIN_STACK_NAME --query 'Stacks[0].Outputs[?OutputKey==\`SearchClusterStackName\`].OutputValue' --output text --region $AWS_DEFAULT_REGION`
if [ -z $SEARCH_STACK_NAME ] ; then
	echo "Cannot find a Search Stack deployed with Antiope. Aborting...."
	exit 0
fi

echo "Discovered Search Stack is $SEARCH_STACK_NAME"
scripts_dir=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
echo "Scripts are located in $scripts_dir"

#
# Index Mapping Creation
#
for index in $INDICES ; do
	$scripts_dir/create_index.py --domain $MAIN_STACK_NAME --index $index --mapping_dir $scripts_dir/../mappings-v7
done

