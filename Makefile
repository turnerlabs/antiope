

# Hardcode this, or submit it on the CLI
export STACK_NAME ?= turner-antiope-dev
export SEARCH_STACK ?= turner-antiope-search-dev


ifndef version
	export version := $(shell date +%Y%b%d-%H%M)
endif

export DEPLOYBUCKET ?= $(STACK_NAME)

# Shouldn't be overridden
export STACK_TEMPLATE ?= cloudformation/Inventory-Template.yaml
export LAMBDA_PACKAGE ?= antiope-lambda-$(version).zip
export manifest ?= cloudformation/Inventory-Manifest-$(STACK_NAME).yaml
export OBJECT_KEY ?= lambda-packages/$(LAMBDA_PACKAGE)
FUNCTIONS = $(STACK_NAME)-pull-organization-data \
			$(STACK_NAME)-get-billing-data \
			$(STACK_NAME)-instances-securitygroups-inventory \
			$(STACK_NAME)-eni-inventory \
			$(STACK_NAME)-vpc-inventory \
			$(STACK_NAME)-route53-inventory \
			$(STACK_NAME)-bucket-inventory \
			$(STACK_NAME)-iam-inventory \
			$(STACK_NAME)-health-inventory




# Search Stack Vars
export SEARCH_STACK_TEMPLATE ?= cloudformation/SearchCluster-Template.yaml
export SEARCH_MANIFEST ?= cloudformation/SearchCluster-Manifest-$(SEARCH_STACK).yaml
export SEARCH_LAMBDA_PACKAGE ?= antiope-lambda-search-$(version).zip
export SEARCH_OBJECT_KEY ?= lambda-packages/$(SEARCH_LAMBDA_PACKAGE)
SEARCH_FUNCTIONS = $(SEARCH_STACK)-ingest-s3



.PHONY: $(FUNCTIONS) $(SEARCH_FUNCTIONS)

# Run all tests
test: cfn-validate
	cd inventory-lambda && $(MAKE) test
	cd search-lambda && $(MAKE) test

deploy: package upload cfn-deploy

clean:
	cd inventory-lambda && $(MAKE) clean
	cd search-lambda && $(MAKE) clean

#
# Cloudformation Targets
#

# Validate the template
cfn-validate: $(STACK_TEMPLATE)
	aws cloudformation validate-template --region us-east-1 --template-body file://$(STACK_TEMPLATE) 1> /dev/null
	aws cloudformation validate-template --region us-east-1 --template-body file://$(SEARCH_STACK_TEMPLATE) 1> /dev/null

# Deploy the stack
cfn-deploy: cfn-validate $(manifest)
	deploy_stack.rb -m $(manifest) pLambdaZipFile=$(OBJECT_KEY) pDeployBucket=$(DEPLOYBUCKET) --force

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



# Search Stack Targets
search-deploy: search-package search-upload search-deploy

search-package:
	cd search-lambda && $(MAKE) package

search-upload: search-package
	aws s3 cp search-lambda/$(SEARCH_LAMBDA_PACKAGE) s3://$(DEPLOYBUCKET)/$(SEARCH_OBJECT_KEY)

search-deploy: cfn-validate $(SEARCH_MANIFEST)
	deploy_stack.rb -m $(SEARCH_MANIFEST) pLambdaZipFile=$(SEARCH_OBJECT_KEY) pDeployBucket=$(DEPLOYBUCKET) --force

search-update: search-package $(SEARCH_FUNCTIONS)
	for f in $(SEARCH_FUNCTIONS) ; do \
	  aws lambda update-function-code --function-name $$f --zip-file fileb://search-lambda/$(SEARCH_LAMBDA_PACKAGE) ; \
	done
