
ifndef env
# $(error env is not set)
	env ?= dev
endif

include config.$(env)
export


ifndef STACK_PREFIX
$(error STACK_PREFIX is not set)
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
MAIN_STACK_NAME=$(STACK_PREFIX)-antiope
OUTPUT_TEMPLATE=$(OUTPUT_TEMPLATE_PREFIX)-$(version).yaml
TEMPLATE_URL ?= https://s3.amazonaws.com/$(BUCKET)/$(DEPLOY_PREFIX)/$(OUTPUT_TEMPLATE)

# Layer Targets
layer:
	cd lambda_layer && $(MAKE) layer


test:
	cd aws-inventory && $(MAKE) test
	cd search-cluster && $(MAKE) test
	cd cognito && $(MAKE) test


# Stack Targets

deploy: package cft-deploy push-config

package:
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
	cft-deploy -m $(MANIFEST) --template-url $(TEMPLATE_URL) pBucketName=$(BUCKET) pAWSLambdaLayerPackage=$(LAYER_URL) --force



# target to generate a manifest file. Only do this once
# we use a lowercase manifest to force the user to specify on the command line and not overwrite existing one
manifest:
ifndef manifest
	$(error manifest is not set)
endif
	cft-generate-manifest -t $(MAIN_TEMPLATE) -m $(manifest) --stack-name $(MAIN_STACK_NAME) --region $(AWS_DEFAULT_REGION)

# Validate all the CFTs. Inventory is so large it can only be validated from S3
cft-validate:
	cft-validate -t cognito/cloudformation/Cognito-Template.yaml
	cft-validate -t search-cluster/cloudformation/SearchCluster-Template.yaml
	@aws s3 cp aws-inventory/cloudformation/Inventory-Template.yaml s3://$(BUCKET)/$(DEPLOY_PREFIX)/validate/Inventory-Template.yaml
	cft-validate --region $(AWS_DEFAULT_REGION) --s3-url s3://$(BUCKET)/$(DEPLOY_PREFIX)/validate/Inventory-Template.yaml
# 	@aws s3 rm s3://$(BUCKET)/$(DEPLOY_PREFIX)/validate/Inventory-Template.yaml

# Clean up dev artifacts
clean:
	cd aws-inventory && $(MAKE) clean
	cd search-cluster && $(MAKE) clean
	cd lambda_layer && $(MAKE) clean
	cd lib && rm -f *.pyc
	rm cloudformation/$(OUTPUT_TEMPLATE_PREFIX)*

push-config:
	@aws s3 cp $(MANIFEST) s3://$(BUCKET)/${CONFIG_PREFIX}/$(MANIFEST)
	@aws s3 cp config.$(env) s3://$(BUCKET)/${CONFIG_PREFIX}/config.$(env)

pull-config:
	aws s3 sync s3://$(BUCKET)/${CONFIG_PREFIX}/ .

sync-resources:
	aws s3 sync s3://$(BUCKET)/Resources/$(type) Scratch/Resources/$(env)/$(type)
	open Scratch/Resources/$(env)/$(type)

sync-reports:
	aws s3 sync s3://$(BUCKET)/Reports Scratch/Reports/$(STACK_PREFIX)-$(env)
	open Scratch/Reports/$(STACK_PREFIX)-$(env)

sync-deploy-package:
	aws s3 sync s3://$(BUCKET)/$(DEPLOY_PREFIX)/ Scratch/$(DEPLOY_PREFIX)/ --delete

purge-deploy-package:
	aws s3 rm s3://$(BUCKET)/$(DEPLOY_PREFIX)/ --recursive



pep8:
	cd aws-inventory/lambda && $(MAKE) pep8
	cd search-cluster/lambda && $(MAKE) pep8
	pycodestyle lib


trigger-inventory:
	./bin/trigger_inventory.sh $(STACK_PREFIX)-$(env)-aws-inventory

disable-inventory:
	$(eval EVENT := $(shell aws cloudformation describe-stacks --stack-name $(STACK_PREFIX)-$(env)-aws-inventory --query 'Stacks[0].Outputs[?OutputKey==`TriggerEventName`].OutputValue' --output text --region $(AWS_DEFAULT_REGION)))
	aws events disable-rule --name $(EVENT) --output text --region $(AWS_DEFAULT_REGION)

enable-inventory:
	$(eval EVENT := $(shell aws cloudformation describe-stacks --stack-name $(STACK_PREFIX)-$(env)-aws-inventory --query 'Stacks[0].Outputs[?OutputKey==`TriggerEventName`].OutputValue' --output text --region $(AWS_DEFAULT_REGION)))
	aws events enable-rule --name $(EVENT) --output text --region $(AWS_DEFAULT_REGION)

get-inventory-errors:
	$(eval QUEUE := $(shell aws cloudformation describe-stacks --stack-name $(STACK_PREFIX)-$(env)-aws-inventory --query 'Stacks[0].Outputs[?OutputKey==`ErrorQueue`].OutputValue' --output text --region $(AWS_DEFAULT_REGION)))
	./bin/pull_errors.py --queue $(QUEUE) --filename $(STACK_PREFIX)-$(env)-aws-inventory-Errors.html --delete
	open $(STACK_PREFIX)-$(env)-aws-inventory-Errors.html
