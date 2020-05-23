
ifndef env
# $(error env is not set)
	env ?= dev
endif

include config.$(env)
export


ifndef MAIN_STACK_NAME
$(error MAIN_STACK_NAME is not set)
endif

ifndef BUCKET
$(error BUCKET is not set)
endif

ifndef version
	export version := $(shell date +%Y%b%d-%H%M)
endif


# Global Vars
export DEPLOY_PREFIX=deploy-packages

# Local to this Makefile Vars
CONFIG_PREFIX=config-files
MAIN_TEMPLATE=cloudformation/antiope-Template.yaml
OUTPUT_TEMPLATE_PREFIX=antiope-Template-Transformed
OUTPUT_TEMPLATE=$(OUTPUT_TEMPLATE_PREFIX)-$(version).yaml
TEMPLATE_URL ?= https://s3.amazonaws.com/$(BUCKET)/$(DEPLOY_PREFIX)/$(OUTPUT_TEMPLATE)

# Layer Targets
layer:
	cd lambda_layer && $(MAKE) layer


test:
	cd aws-inventory && $(MAKE) test
	cd search-cluster && $(MAKE) test
	cd cognito && $(MAKE) test


deps:
	cd aws-inventory/lambda && $(MAKE) deps
# 	cd search-cluster/lambda $(MAKE) deps


#
# Deploy New Code Targets
#

# Deploy a fresh version of code
deploy: cft-validate package cft-deploy push-config

package: deps
	@aws cloudformation package --template-file $(MAIN_TEMPLATE) --s3-bucket $(BUCKET) --s3-prefix $(DEPLOY_PREFIX)/transform --output-template-file cloudformation/$(OUTPUT_TEMPLATE)  --metadata build_ver=$(version)
	@aws s3 cp cloudformation/$(OUTPUT_TEMPLATE) s3://$(BUCKET)/$(DEPLOY_PREFIX)/
	rm cloudformation/$(OUTPUT_TEMPLATE)

cft-deploy: package
ifndef MANIFEST
	$(error MANIFEST is not set)
endif
ifndef LAYER_URL
	$(error LAYER_URL is not set)
endif
	cft-deploy -m $(MANIFEST) --template-url $(TEMPLATE_URL) pTemplateURL=$(TEMPLATE_URL) pBucketName=$(BUCKET) pAWSLambdaLayerPackage=$(LAYER_URL) --force


post-deploy:
	cd aws-inventory && $(MAKE) post-deploy
	cd cognito && $(MAKE) post-deploy

#
# Promote Existing Code Targets
#

# promote an existing stack to a new environment
# Assumes cross-account access to the lower environment's DEPLOY_PREFIX
promote: cft-promote push-config

cft-promote:
ifndef MANIFEST
	$(error MANIFEST is not set)
endif
ifndef LAYER_URL
	$(error LAYER_URL is not set)
endif
ifndef template
	$(error template is not set)
endif
	cft-deploy -m $(MANIFEST) --template-url $(template) pTemplateURL=$(template) pBucketName=$(BUCKET) pAWSLambdaLayerPackage=$(LAYER_URL) --force


#
# Testing & Cleanup Targets
#
# Validate all the CFTs. Inventory is so large it can only be validated from S3
cft-validate:
	cft-validate -t cloudformation/antiope-Template.yaml
	cft-validate -t cognito/cloudformation/Cognito-Template.yaml
	cft-validate -t search-cluster/cloudformation/SearchCluster-Template.yaml
	@aws s3 cp aws-inventory/cloudformation/Inventory-Template.yaml s3://$(BUCKET)/$(DEPLOY_PREFIX)/validate/Inventory-Template.yaml
	aws cloudformation validate-template --template-url https://s3.amazonaws.com/$(BUCKET)/$(DEPLOY_PREFIX)/validate/Inventory-Template.yaml > /dev/null
	@aws s3 rm s3://$(BUCKET)/$(DEPLOY_PREFIX)/validate/Inventory-Template.yaml

# Clean up dev artifacts
clean:
	cd aws-inventory && $(MAKE) clean
	cd search-cluster && $(MAKE) clean
	cd lambda_layer && $(MAKE) clean
	cd lib && rm -f *.pyc
	rm cloudformation/$(OUTPUT_TEMPLATE_PREFIX)*

pep8:
	cd aws-inventory/lambda && $(MAKE) pep8
	cd search-cluster/lambda && $(MAKE) pep8

purge-deploy-packages:
	aws s3 rm s3://$(BUCKET)/$(DEPLOY_PREFIX)/ --recursive

sync-deploy-packages:
	aws s3 sync s3://$(BUCKET)/$(DEPLOY_PREFIX)/ Scratch/$(DEPLOY_PREFIX)/ --delete

#
# Management Targets
#


# target to generate a manifest file. Only do this once
# we use a lowercase manifest to force the user to specify on the command line and not overwrite existing one
manifest:
ifndef manifest
	$(error manifest is not set)
endif
	cft-generate-manifest -t $(MAIN_TEMPLATE) -m $(manifest) --stack-name $(MAIN_STACK_NAME) --region $(AWS_DEFAULT_REGION)

push-config:
	@aws s3 cp $(MANIFEST) s3://$(BUCKET)/${CONFIG_PREFIX}/$(MANIFEST)
	@aws s3 cp config.$(env) s3://$(BUCKET)/${CONFIG_PREFIX}/config.$(env)

pull-config:
	aws s3 sync s3://$(BUCKET)/${CONFIG_PREFIX}/ .

sync-resources:
	aws s3 sync s3://$(BUCKET)/Resources/$(type) Scratch/Resources/$(env)/$(type)
	open Scratch/Resources/$(env)/$(type)

sync-reports:
	aws s3 sync s3://$(BUCKET)/Reports Scratch/Reports/$(MAIN_STACK_NAME)
	open Scratch/Reports/$(MAIN_STACK_NAME)

trigger-inventory:
	@./bin/trigger_inventory.sh $(MAIN_STACK_NAME)

disable-inventory:
	$(eval EVENT := $(shell aws cloudformation describe-stacks --stack-name $(MAIN_STACK_NAME) --query 'Stacks[0].Outputs[?OutputKey==`TriggerEventName`].OutputValue' --output text --region $(AWS_DEFAULT_REGION)))
	aws events disable-rule --name $(EVENT) --output text --region $(AWS_DEFAULT_REGION)

enable-inventory:
	$(eval EVENT := $(shell aws cloudformation describe-stacks --stack-name $(MAIN_STACK_NAME) --query 'Stacks[0].Outputs[?OutputKey==`TriggerEventName`].OutputValue' --output text --region $(AWS_DEFAULT_REGION)))
	aws events enable-rule --name $(EVENT) --output text --region $(AWS_DEFAULT_REGION)

get-inventory-errors:
	$(eval QUEUE := $(shell aws cloudformation describe-stacks --stack-name $(MAIN_STACK_NAME) --query 'Stacks[0].Outputs[?OutputKey==`ErrorQueue`].OutputValue' --output text --region $(AWS_DEFAULT_REGION)))
	./bin/pull_errors.py --queue $(QUEUE) --filename $(MAIN_STACK_NAME)-Errors.html --delete
	open $(MAIN_STACK_NAME)-Errors.html
