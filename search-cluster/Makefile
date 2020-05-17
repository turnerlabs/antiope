

ifndef env
# $(error env is not set)
	env ?= dev
endif

include ../config.$(env)
export

# STACK_PREFIX is custom to your deployment and should be the same for all Antiope Stacks
ifndef STACK_PREFIX
	$(error STACK_PREFIX is not set)
endif

ifndef BUCKET
	$(error BUCKET is not set)
endif

ifndef version
	export version := $(shell date +%Y%b%d-%H%M)
endif

# Indicies should be singular!
INDICES=resources_accessanalyzer_analyzer \
		resources_cloudformation_stack \
		resources_cloudfront_distribution \
		resources_cloudtrail_trail \
		resources_ec2_ami \
		resources_ec2_eni \
		resources_ec2_instance \
		resources_ec2_securitygroup \
		resources_ec2_snapshot \
		resources_ec2_volume \
		resources_ec2_vpc \
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
		resources_rds_dbcluster \
		resources_rds_dbinstance \
		resources_redshift_clusters \
		resources_route53_domain \
		resources_route53_hostedzone \
		resources_s3_bucket \
		resources_sagemaker_notebook \
		resources_secretsmanager_secret \
		resources_ssm_managedinstance \
		resources_support_case \
		resources_support_trustedadvisorcheckresult

# Specific to this stack
RESOURCE_PREFIX=$(STACK_PREFIX)-antiope-search-cluster

# Name of the Zip file with all the function code and dependencies
export LAMBDA_PACKAGE ?= $(RESOURCE_PREFIX)-lambda-$(version).zip

export MAIN_STACK_NAME=$(STACK_PREFIX)-antiope

# List of all the functions deployed by this stack. Required for "make update" to work.
FUNCTIONS = $(RESOURCE_PREFIX)-ingest-s3

.PHONY: $(FUNCTIONS)

#
# Lambda Targets
#
test:
	cd lambda && $(MAKE) test

clean:
	cd lambda && $(MAKE) clean
	cd scripts && $(MAKE) clean
	rm -f notification_template-$(STACK_PREFIX).json

package:
	cd lambda && $(MAKE) package

# # Update the Lambda Code without modifying the CF Stack
update: package $(FUNCTIONS)
	for f in $(FUNCTIONS) ; do \
	  aws lambda update-function-code --region $(AWS_DEFAULT_REGION) --function-name $$f --zip-file fileb://lambda/$(LAMBDA_PACKAGE) ; \
	done

# Update one specific function. Called as "make fupdate function=<fillinstackprefix>-aws-inventory-ecs-inventory"
fupdate: package
	aws lambda update-function-code --region $(AWS_DEFAULT_REGION) --function-name $(function) --zip-file fileb://lambda/$(LAMBDA_PACKAGE) ; \

#
# Post Deploy Targets
#
post-deploy: enable-s3-events indices expire-logs enable-kibana-auth

enable-s3-events:
	$(eval SEARCH_STACK_NAME := $(shell aws cloudformation describe-stacks --stack-name $(MAIN_STACK_NAME) --query 'Stacks[0].Outputs[?OutputKey==`SearchClusterStackName`].OutputValue' --output text --region $(AWS_DEFAULT_REGION)))
	$(eval QUEUEARN := $(shell aws --region $(AWS_DEFAULT_REGION) cloudformation describe-stacks --stack-name $(SEARCH_STACK_NAME) --query 'Stacks[0].Outputs[?OutputKey==`SearchIngestEventQueueArn`].OutputValue' --output text))
	cat notification_template.json | jq '.QueueConfigurations[0].QueueArn = "$(QUEUEARN)"' > notification_template-$(STACK_PREFIX).json
	aws --region $(AWS_DEFAULT_REGION) s3api put-bucket-notification-configuration --bucket $(BUCKET) --notification-configuration file://notification_template-$(STACK_PREFIX).json
	rm notification_template-$(STACK_PREFIX).json

enable-kibana-auth:
	$(eval SEARCH_STACK_NAME := $(shell aws cloudformation describe-stacks --stack-name $(MAIN_STACK_NAME) --query 'Stacks[0].Outputs[?OutputKey==`SearchClusterStackName`].OutputValue' --output text --region $(AWS_DEFAULT_REGION)))
	$(eval COGNITO_STACK_NAME := $(shell aws cloudformation describe-stacks --stack-name $(MAIN_STACK_NAME) --query 'Stacks[0].Outputs[?OutputKey==`CognitoStackName`].OutputValue' --output text --region $(AWS_DEFAULT_REGION)))
	$(eval DOMAIN := $(shell aws cloudformation describe-stacks --stack-name $(SEARCH_STACK_NAME) --query 'Stacks[0].Outputs[?OutputKey==`ClusterName`].OutputValue' --output text --region $(AWS_DEFAULT_REGION)))
	$(eval ROLE := $(shell aws cloudformation describe-stacks --stack-name $(SEARCH_STACK_NAME) --query 'Stacks[0].Outputs[?OutputKey==`ESCognitoRoleArn`].OutputValue' --output text --region $(AWS_DEFAULT_REGION)))
	$(eval USER_POOL_ID := $(shell aws cloudformation describe-stacks --stack-name $(COGNITO_STACK_NAME) --query 'Stacks[0].Outputs[?OutputKey==`CognitoUserPoolId`].OutputValue' --output text --region $(AWS_DEFAULT_REGION)))
	$(eval ID_POOL_ID := $(shell aws cloudformation describe-stacks --stack-name $(COGNITO_STACK_NAME) --query 'Stacks[0].Outputs[?OutputKey==`CognitoIdentityPoolId`].OutputValue' --output text --region $(AWS_DEFAULT_REGION)))
	aws --region $(AWS_DEFAULT_REGION) es update-elasticsearch-domain-config --domain-name $(DOMAIN) --cognito-options Enabled=true,UserPoolId=$(USER_POOL_ID),IdentityPoolId=$(ID_POOL_ID),RoleArn=$(ROLE)

script-deps:
	cd scripts && $(MAKE) deps

expire-logs:
	for f in $(FUNCTIONS) ; do \
	  aws --region $(AWS_DEFAULT_REGION) logs put-retention-policy --log-group-name /aws/lambda/$$f --retention-in-days 5 ; \
	done

indices: script-deps
	for i in $(INDICES) ; do \
	  ./scripts/create_index.py --domain $(STACK_PREFIX) --index $$i --mapping_dir mappings ; \
	done

index: script-deps
	./scripts/create_index.py --domain $(STACK_PREFIX) --index $(index) --mapping_dir mappings --delete


#
# House Cleaning Functions (for the Purge)
#

purge-indices: script-deps
	$(eval SEARCH_STACK_NAME := $(shell aws cloudformation describe-stacks --stack-name $(MAIN_STACK_NAME) --query 'Stacks[0].Outputs[?OutputKey==`SearchClusterStackName`].OutputValue' --output text --region $(AWS_DEFAULT_REGION)))
	$(eval DOMAIN := $(shell aws cloudformation describe-stacks --stack-name $(SEARCH_STACK_NAME) --query 'Stacks[0].Outputs[?OutputKey==`ClusterName`].OutputValue' --output text --region $(AWS_DEFAULT_REGION)))
	for i in $(INDICES) ; do \
	  ./scripts/create_index.py --domain $(DOMAIN) --index $$i --mapping_dir mappings --delete ; \
	done

purge-logs:
	for f in $(FUNCTIONS) ; do \
	  aws --region $(AWS_DEFAULT_REGION) logs delete-log-group --log-group-name /aws/lambda/$$f ; \
	done


