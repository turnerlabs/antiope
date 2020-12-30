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
#### Kibana Auth can now be done via CloudFormation. Bout Damn Time #####
# COGNITO_STACK_NAME=`aws cloudformation describe-stacks --stack-name $MAIN_STACK_NAME --query 'Stacks[0].Outputs[?OutputKey==\`CognitoStackName\`].OutputValue' --output text --region $AWS_DEFAULT_REGION`
# DOMAIN=`aws cloudformation describe-stacks --stack-name $SEARCH_STACK_NAME --query 'Stacks[0].Outputs[?OutputKey==\`ClusterName\`].OutputValue' --output text --region $AWS_DEFAULT_REGION`
# ROLE=`aws cloudformation describe-stacks --stack-name $SEARCH_STACK_NAME --query 'Stacks[0].Outputs[?OutputKey==\`ESCognitoRoleArn\`].OutputValue' --output text --region $AWS_DEFAULT_REGION`
# USER_POOL_ID=`aws cloudformation describe-stacks --stack-name $COGNITO_STACK_NAME --query 'Stacks[0].Outputs[?OutputKey==\`CognitoUserPoolId\`].OutputValue' --output text --region $AWS_DEFAULT_REGION`
# ID_POOL_ID=`aws cloudformation describe-stacks --stack-name $COGNITO_STACK_NAME --query 'Stacks[0].Outputs[?OutputKey==\`CognitoIdentityPoolId\`].OutputValue' --output text --region $AWS_DEFAULT_REGION`
# aws es update-elasticsearch-domain-config --domain-name ${DOMAIN} --cognito-options Enabled=true,UserPoolId=${USER_POOL_ID},IdentityPoolId=${ID_POOL_ID},RoleArn=${ROLE} --region ${AWS_DEFAULT_REGION}
# if [ $? -ne 0 ] ; then
# 	echo "WARNING - Issue creating Kibana for the Elastic Search Cluster. You may need to investigate and run this script again"
# fi

#
# Index Mapping Creation
#
$scripts_dir/make_all_indicies.sh

