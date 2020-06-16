#!/bin/bash

# Execute Post-Deploy steps for Cognito Stack

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

export COGNITO_STACK_NAME=`aws cloudformation describe-stacks --stack-name $MAIN_STACK_NAME --query 'Stacks[0].Outputs[?OutputKey==\`CognitoStackName\`].OutputValue' --output text --region $AWS_DEFAULT_REGION`
echo "Discovered Cognito Stack is $COGNITO_STACK_NAME"

ID=`aws cloudformation describe-stacks --stack-name $COGNITO_STACK_NAME --query 'Stacks[0].Outputs[?OutputKey==\`CognitoUserPoolId\`].OutputValue' --output text --region $AWS_DEFAULT_REGION`
if [ -z "`aws cognito-idp describe-user-pool-domain --domain $MAIN_STACK_NAME  --output text --region $AWS_DEFAULT_REGION`" ] ; then
	echo "Configuring Cognito domain $MAIN_STACK_NAME for $ID"
	aws cognito-idp create-user-pool-domain --user-pool-id $ID --domain $MAIN_STACK_NAME --region $AWS_DEFAULT_REGION
else
	echo "Cognito already configured for $ID"
fi

# aws cognito-idp  delete-user-pool-domain --user-pool-id $ID --domain $MAIN_STACK_NAME --region us-east-1