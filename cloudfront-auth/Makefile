

include ../config.env
export

# STACK_PREFIX is custom to your deployment and should be the same for all Antiope Stacks
ifndef STACK_PREFIX
	$(error STACK_PREFIX is not set)
endif

ifndef BUCKET
	$(error BUCKET is not set)
endif

ifndef env
# $(error env is not set)
	env ?= dev
endif

ifndef version
	export version := $(shell date +%Y%b%d-%H%M)
endif

# Specific to this stack
export STACK_NAME=auth
# Filename for the CFT to deploy
export STACK_TEMPLATE=cloudformation/Auth-Template.yaml

# Name of the Zip file with all the function code and dependencies
export LAMBDA_PACKAGE=$(STACK_NAME)-lambda-$(version).zip

# The full name of the stack in Cloudformation. This must match the manifest file
export FULL_STACK_NAME=$(STACK_PREFIX)-$(env)-$(STACK_NAME)

# Name of the manifest file.
export manifest=cloudformation/$(FULL_STACK_NAME)-Manifest.yaml

# location in the Antiope bucket where we drop lambda-packages
export OBJECT_KEY=deploy-packages/$(LAMBDA_PACKAGE)

# List of all the functions deployed by this stack. Required for "make update" to work.
export EDGE_NAME=$(FULL_STACK_NAME)-edge-lambda

# Run all tests
test: cfn-validate
	cd lambda && $(MAKE) test

# Do everything
deploy: package upload cfn-deploy html-deploy edge-deploy

clean:
	cd lambda && $(MAKE) clean

#
# Cloudformation Targets
#

# Validate the template
cfn-validate: $(STACK_TEMPLATE)
	aws cloudformation validate-template --region us-east-1 --template-body file://$(STACK_TEMPLATE)

# Deploy the stack
cfn-deploy: cfn-validate $(manifest)
	deploy_stack.rb -m $(manifest) pLambdaZipFile=$(OBJECT_KEY) pBucketName=$(BUCKET) pEnvironment=$(env)  --force

#
# Lambda Targets
#
package:
	cd lambda && $(MAKE) package

upload: package
	aws s3 cp lambda/$(LAMBDA_PACKAGE) s3://$(BUCKET)/$(OBJECT_KEY)


html-deploy:
	bin/deploy-html.sh

edge-deploy:
	bin/deploy-edge.sh
