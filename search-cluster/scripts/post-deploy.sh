#!/bin/bash

if [ -z $MAIN_STACK_NAME ] ; then
  echo "MAIN_STACK_NAME is not in the environment, is this being executed from makefile or with env config.ENV"
  exit 1
fi

if [ -z $BUCKET ] ; then
  echo "BUCKET is not in the environment, is this being executed from makefile or with env config.ENV"
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
INDICES="	resources_accessanalyzer_analyzer \
			resources_accessanalyzer_finding \
			resources_cloudformation_stack \
			resources_cloudfront_distribution \
			resources_cloudtrail_trail \
			resources_dx_connection \
			resources_dx_gw \
			resources_dx_vif \
			resources_ec2_ami \
			resources_ec2_eni \
			resources_ec2_instance \
			resources_ec2_securitygroup \
			resources_ec2_snapshot \
			resources_ec2_transitgateway \
			resources_ec2_volume \
			resources_ec2_vpc \
			resources_ec2_clientvpn \
			resources_ecr_repository \
			resources_ecs_cluster \
			resources_ecs_task \
			resources_elb_loadbalancer \
			resources_elbv2_loadbalancer \
			resources_es_domain \
			resources_guardduty_detector \
			resources_iam_role \
			resources_iam_saml \
			resources_iam_user \
			resources_kms_key \
			resources_lambda_function \
			resources_lambda_layer \
			resources_rds_dbcluster \
			resources_rds_dbinstance \
			resources_redshift_clusters \
			resources_route53_domain \
			resources_route53_hostedzone \
			resources_s3_bucket \
			resources_sagemaker_notebook \
			resources_secretsmanager_secret \
			resources_shield_attacks \
			resources_shield_protection \
			resources_shield_subscription \
			resources_ssm_managedinstance \
			resources_support_case \
			resources_wafv2_webacl \
			resources_worklink_fleet \
			resources_support_trustedadvisorcheckresult \
			azure_resources_vm_instance"

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
# S3 Event To SQS
#
QUEUEARN=`aws cloudformation describe-stacks --stack-name $SEARCH_STACK_NAME --query 'Stacks[0].Outputs[?OutputKey==\`SearchIngestEventQueueArn\`].OutputValue' --output text --region $AWS_DEFAULT_REGION`
read -r -d '' TEMPLATE << ENDJSON
{
  "QueueConfigurations": [
    {
      "Id": "elastic-ingest",
      "QueueArn": "$QUEUEARN",
      "Events": [
        "s3:ObjectCreated:Put"
      ],
      "Filter": {
        "Key": {
          "FilterRules": [
            {
              "Name": "Prefix",
              "Value": "Resources/"
            },
            {
              "Name": "Suffix",
              "Value": ".json"
            }
          ]
        }
      }
    }
  ]
}
ENDJSON
echo "Applying Event Notification for AWS Resources to $QUEUEARN"
# TODO - this will overwrite any other events for the bucket. Best would be to get the existing config and then apply on the needed change
aws s3api put-bucket-notification-configuration --bucket ${BUCKET} --notification-configuration "$TEMPLATE"


#
# Kibana Auth
#
COGNITO_STACK_NAME=`aws cloudformation describe-stacks --stack-name $MAIN_STACK_NAME --query 'Stacks[0].Outputs[?OutputKey==\`CognitoStackName\`].OutputValue' --output text --region $AWS_DEFAULT_REGION`
DOMAIN=`aws cloudformation describe-stacks --stack-name $SEARCH_STACK_NAME --query 'Stacks[0].Outputs[?OutputKey==\`ClusterName\`].OutputValue' --output text --region $AWS_DEFAULT_REGION`
ROLE=`aws cloudformation describe-stacks --stack-name $SEARCH_STACK_NAME --query 'Stacks[0].Outputs[?OutputKey==\`ESCognitoRoleArn\`].OutputValue' --output text --region $AWS_DEFAULT_REGION`
USER_POOL_ID=`aws cloudformation describe-stacks --stack-name $COGNITO_STACK_NAME --query 'Stacks[0].Outputs[?OutputKey==\`CognitoUserPoolId\`].OutputValue' --output text --region $AWS_DEFAULT_REGION`
ID_POOL_ID=`aws cloudformation describe-stacks --stack-name $COGNITO_STACK_NAME --query 'Stacks[0].Outputs[?OutputKey==\`CognitoIdentityPoolId\`].OutputValue' --output text --region $AWS_DEFAULT_REGION`
aws es update-elasticsearch-domain-config --domain-name ${DOMAIN} --cognito-options Enabled=true,UserPoolId=${USER_POOL_ID},IdentityPoolId=${ID_POOL_ID},RoleArn=${ROLE} --region ${AWS_DEFAULT_REGION}
if [ $? -ne 0 ] ; then
	echo "WARNING - Issue creating Kibana for the Elastic Search Cluster. You may need to investigate and run this script again"
fi

#
# Index Mapping Creation
#
for index in $INDICES ; do
	$scripts_dir/create_index.py --domain $MAIN_STACK_NAME --index $index --mapping_dir $scripts_dir/../mappings
done

