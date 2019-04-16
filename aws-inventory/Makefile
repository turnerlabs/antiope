
ifndef env
# $(error env is not set)
	env ?= dev
endif

ifdef CONFIG
	include ../$(CONFIG)
	export
else
	include ../config.$(env)
	export
endif

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

# Specific to this stack
export STACK_NAME=aws-inventory
# Filename for the CFT to deploy
export STACK_TEMPLATE=cloudformation/Inventory-Template.yaml

# Name of the Zip file with all the function code and dependencies
export LAMBDA_PACKAGE=$(STACK_NAME)-lambda-$(version).zip

# The full name of the stack in Cloudformation. This must match the manifest file
export FULL_STACK_NAME=$(STACK_PREFIX)-$(env)-$(STACK_NAME)

# Name of the manifest file.
export manifest=cloudformation/$(FULL_STACK_NAME)-Manifest.yaml

# location in the Antiope bucket where we drop lambda-packages
export OBJECT_KEY=deploy-packages/$(LAMBDA_PACKAGE)

# For uploading CFT to S3
export TEMPLATE_KEY ?= deploy-packages/$(STACK_NAME)-Template-$(version).yaml
export TEMPLATE_URL ?= https://s3.amazonaws.com/$(BUCKET)/$(TEMPLATE_KEY)

# List of all the functions deployed by this stack. Required for "make update" to work.
FUNCTIONS = $(FULL_STACK_NAME)-pull-organization-data \
			$(FULL_STACK_NAME)-trigger-inventory \
			$(FULL_STACK_NAME)-get-billing-data \
			$(FULL_STACK_NAME)-instances-sg-inventory \
			$(FULL_STACK_NAME)-eni-inventory \
			$(FULL_STACK_NAME)-vpc-inventory \
			$(FULL_STACK_NAME)-route53-inventory \
			$(FULL_STACK_NAME)-bucket-inventory \
			$(FULL_STACK_NAME)-iam-inventory \
			$(FULL_STACK_NAME)-ecs-inventory \
			$(FULL_STACK_NAME)-es-inventory \
			$(FULL_STACK_NAME)-cloudtrail-inventory \
			$(FULL_STACK_NAME)-secrets-inventory \
			$(FULL_STACK_NAME)-health-inventory \
			$(FULL_STACK_NAME)-ecr-inventory \
			$(FULL_STACK_NAME)-lambdas-inventory \
			$(FULL_STACK_NAME)-kms-inventory \
			$(FULL_STACK_NAME)-dx-inventory \
			$(FULL_STACK_NAME)-ssm-inventory \
			$(FULL_STACK_NAME)-ta-inventory \
			$(FULL_STACK_NAME)-support-inventory \
			$(FULL_STACK_NAME)-ami-inventory \
			$(FULL_STACK_NAME)-cloudformation-inventory \
			$(FULL_STACK_NAME)-cloudfront-inventory \
			$(FULL_STACK_NAME)-create-account-report \
			$(FULL_STACK_NAME)-create-foreign-account-report \
			$(FULL_STACK_NAME)-create-vpc-report \
			$(FULL_STACK_NAME)-new_account_handler


.PHONY: $(FUNCTIONS)

# Run all tests
test: cfn-validate
	cd lambda && $(MAKE) test

# Do everything
deploy: package upload cfn-deploy templates upload-config

clean:
	cd lambda && $(MAKE) clean

#
# Cloudformation Targets
#

# Upload template to S3
cfn-upload: $(STACK_TEMPLATE)
	aws s3 cp $(STACK_TEMPLATE) s3://$(BUCKET)/$(TEMPLATE_KEY)

# Validate the template
cfn-validate: cfn-upload $(STACK_TEMPLATE)
	cft-validate --region $(AWS_DEFAULT_REGION) --s3-url s3://$(BUCKET)/$(TEMPLATE_KEY)

# Deploy the stack
cfn-deploy: cfn-validate $(manifest)
	cft-deploy -m $(manifest) --template-url $(TEMPLATE_URL) pLambdaZipFile=$(OBJECT_KEY) pBucketName=$(BUCKET)  --force

#
# Lambda Targets
#
package:
	cd lambda && $(MAKE) package

zipfile:
	cd lambda && $(MAKE) zipfile

upload: package
	aws s3 cp lambda/$(LAMBDA_PACKAGE) s3://$(BUCKET)/$(OBJECT_KEY)

# # Update the Lambda Code without modifying the CF Stack
update: package $(FUNCTIONS)
	for f in $(FUNCTIONS) ; do \
	  aws lambda update-function-code --function-name $$f --zip-file fileb://lambda/$(LAMBDA_PACKAGE) ; \
	done

# Update one specific function. Called as "make fupdate function=<fillinstackprefix>-aws-inventory-ecs-inventory"
fupdate: zipfile
	aws lambda update-function-code --function-name $(function) --zip-file fileb://lambda/$(LAMBDA_PACKAGE) ; \

#
# Management Targets
#

# This will prompt for confirmation
purge-tables:
	purge_ddb_table.py --table $(FULL_STACK_NAME)-accounts --key_attribute account_id --force
	purge_ddb_table.py --table $(FULL_STACK_NAME)-billing-data --key_attribute account_id --force
	purge_ddb_table.py --table $(FULL_STACK_NAME)-vpc-inventory --key_attribute vpc_id --force

trigger:
	../bin/trigger_inventory.sh $(FULL_STACK_NAME)


templates:
	aws s3 sync html_templates s3://$(BUCKET)/Templates/

purge-logs:
	for f in $(FUNCTIONS) ; do \
	  aws logs delete-log-group --log-group-name /aws/lambda/$$f ; \
	done

expire-logs:
	for f in $(FUNCTIONS) ; do \
	  aws logs put-retention-policy --log-group-name /aws/lambda/$$f --retention-in-days 5 ; \
	done

upload-config:
	aws s3 cp $(FULL_STACK_NAME)-config.json s3://$(BUCKET)/