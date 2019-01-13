
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
export STACK_NAME=cognito
# Filename for the CFT to deploy
export STACK_TEMPLATE=cloudformation/Cognito-Template.yaml

# The full name of the stack in Cloudformation. This must match the manifest file
export FULL_STACK_NAME=$(STACK_PREFIX)-$(env)-$(STACK_NAME)

# Name of the manifest file.
export manifest=cloudformation/$(FULL_STACK_NAME)-Manifest.yaml

# For uploading CFT to S3
export TEMPLATE_KEY ?= deploy-packages/$(STACK_NAME)-Template-$(version).yaml
export TEMPLATE_URL ?= https://s3.amazonaws.com/$(BUCKET)/$(TEMPLATE_KEY)

.PHONY: $(FUNCTIONS)

# Do everything
deploy: cfn-deploy configure-identity-pool

#
# Cloudformation Targets
#

# Upload template to S3
cfn-upload: $(STACK_TEMPLATE)
	aws s3 cp $(STACK_TEMPLATE) s3://$(BUCKET)/$(TEMPLATE_KEY)

# Validate the template
cfn-validate: cfn-upload $(STACK_TEMPLATE)
	aws cloudformation validate-template --region $(AWS_DEFAULT_REGION) --template-url $(TEMPLATE_URL)

# Deploy the stack
cfn-deploy: cfn-validate $(manifest)
	deploy_stack.rb -m $(manifest) --template-url $(TEMPLATE_URL) --force

configure-identity-pool:
	$(eval ID := $(shell aws cloudformation describe-stacks --stack-name $(FULL_STACK_NAME) --query 'Stacks[0].Outputs[?OutputKey==`CognitoUserPoolId`].OutputValue' --output text --region $(AWS_DEFAULT_REGION)))
	-aws --region $(AWS_DEFAULT_REGION) cognito-idp create-user-pool-domain --user-pool-id $(ID) --domain $(STACK_PREFIX)-$(env)