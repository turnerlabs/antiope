
ifndef env
# $(error env is not set)
	env ?= dev
endif

ifdef CONFIG
	include $(CONFIG)
	export
else
	include config.$(env)
	export
endif

ifndef STACK_PREFIX
$(error STACK_PREFIX is not set)
endif

ifndef BUCKET
$(error BUCKET is not set)
endif

everything: cognito-deploy inventory-deploy search-deploy

library:
	cd lambda_layer && $(MAKE) layer

cognito-deploy:
	cd cognito && $(MAKE) deploy

inventory-deploy:
	cd aws-inventory && $(MAKE) deploy

inventory-update:
	cd aws-inventory && $(MAKE) update

search-deploy:
	cd search-cluster && $(MAKE) deploy-all

search-update:
	cd search-cluster && $(MAKE) update

clean:
	cd aws-inventory && $(MAKE) clean
	cd gcp-inventory && $(MAKE) clean
	cd search-cluster && $(MAKE) clean
	cd lambda_layer && $(MAKE) clean
	cd gcp_lambda_layer && $(MAKE) clean
	# cd cognito && $(MAKE) clean

trigger-inventory:
	./bin/trigger_inventory.sh $(STACK_PREFIX)-$(env)-aws-inventory

sync-resources:
	aws s3 sync s3://$(BUCKET)/Resources/$(type) Scratch/Resources/$(env)/$(type)
	open Scratch/Resources/$(env)/$(type)

sync-reports:
	aws s3 sync s3://$(BUCKET)/Reports Scratch/Reports/$(STACK_PREFIX)-$(env)
	open Scratch/Reports/$(STACK_PREFIX)-$(env)

disable-inventory:
	$(eval EVENT := $(shell aws cloudformation describe-stacks --stack-name $(STACK_PREFIX)-$(env)-aws-inventory --query 'Stacks[0].Outputs[?OutputKey==`TriggerEventName`].OutputValue' --output text --region $(AWS_DEFAULT_REGION)))
	aws events disable-rule --name $(EVENT) --output text --region $(AWS_DEFAULT_REGION)

enable-inventory:
	$(eval EVENT := $(shell aws cloudformation describe-stacks --stack-name $(STACK_PREFIX)-$(env)-aws-inventory --query 'Stacks[0].Outputs[?OutputKey==`TriggerEventName`].OutputValue' --output text --region $(AWS_DEFAULT_REGION)))
	aws events enable-rule --name $(EVENT) --output text --region $(AWS_DEFAULT_REGION)

gcp:
	cd gcp_lambda_layer && $(MAKE) layer
	cd gcp-inventory && $(MAKE) deploy
