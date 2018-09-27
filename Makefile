

# Customize these Settings
export STACK_PREFIX ?= FIXME

ifndef env
# $(error env is not set)
	env ?= dev
endif

ifndef version
	export version := $(shell date +%Y%b%d-%H%M)
endif

# Shouldn't be overridden
export STACK_TEMPLATE ?= cloudformation/Inventory-Template.yaml
export LAMBDA_PACKAGE ?= antiope-lambda-$(version).zip
export manifest ?= cloudformation/Inventory-Manifest-$(env).yaml
export STACK_NAME=$(STACK_PREFIX)-$(env)
export OBJECT_KEY ?= lambda-packages/$(LAMBDA_PACKAGE)
export DEPLOYBUCKET ?= $(STACK_NAME)

FUNCTIONS = $(STACK_NAME)-pull-organization-data \
			$(STACK_NAME)-get-billing-data \
			$(STACK_NAME)-instances-securitygroups-inventory \
			$(STACK_NAME)-eni-inventory \
			$(STACK_NAME)-vpc-inventory \
			$(STACK_NAME)-route53-inventory \
			$(STACK_NAME)-bucket-inventory \
			$(STACK_NAME)-iam-inventory \
			$(STACK_NAME)-health-inventory


.PHONY: $(FUNCTIONS)

# Run all tests
test: cfn-validate
	cd inventory-lambda && $(MAKE) test

deploy: package upload cfn-deploy

clean:
	cd inventory-lambda && $(MAKE) clean

#
# Cloudformation Targets
#

# Validate the template
cfn-validate: $(STACK_TEMPLATE)
	aws cloudformation validate-template --region us-east-1 --template-body file://$(STACK_TEMPLATE)

# Deploy the stack
cfn-deploy: cfn-validate $(manifest)
	deploy_stack.rb -m $(manifest) pLambdaZipFile=$(OBJECT_KEY) pDeployBucket=$(DEPLOYBUCKET) pEnvironment=$(env)  --force

#
# Lambda Targets
#
package:
	cd inventory-lambda && $(MAKE) package

upload: package
	aws s3 cp inventory-lambda/$(LAMBDA_PACKAGE) s3://$(DEPLOYBUCKET)/$(OBJECT_KEY)

# # Update the Lambda Code without modifying the CF Stack
update: package $(FUNCTIONS)
	for f in $(FUNCTIONS) ; do \
	  aws lambda update-function-code --function-name $$f --zip-file fileb://inventory-lambda/$(LAMBDA_PACKAGE) ; \
	done


fupdate: package
	aws lambda update-function-code --function-name $(function) --zip-file fileb://inventory-lambda/$(LAMBDA_PACKAGE) ; \

# This will prompt for confirmation
purge:
	purge_ddb_table.py --table $(STACK_TEMPLATE)-accounts --key_attribute account_id --force
	purge_ddb_table.py --table $(STACK_TEMPLATE)-billing-data --key_attribute account_id --force
	purge_ddb_table.py --table $(STACK_TEMPLATE)-vpc-inventory --key_attribute vpc_id --force

trigger:
	./bin/trigger_state_machine.sh $(STACK_NAME)
