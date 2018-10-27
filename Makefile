
include config.env
export

ifndef STACK_PREFIX
$(error STACK_PREFIX is not set)
endif

ifndef BUCKET
$(error BUCKET is not set)
endif


inventory-deploy:
	cd aws-inventory && $(MAKE) deploy

inventory-update:
	cd aws-inventory && $(MAKE) update

clean:
	cd aws-inventory && $(MAKE) clean
	cd search-lambda && $(MAKE) clean

#####


# Search Stack Vars
export SEARCH_STACK_TEMPLATE ?= cloudformation/SearchCluster-Template.yaml
export SEARCH_MANIFEST ?= cloudformation/SearchCluster-Manifest-$(SEARCH_STACK).yaml
export SEARCH_LAMBDA_PACKAGE ?= antiope-lambda-search-$(version).zip
export SEARCH_OBJECT_KEY ?= lambda-packages/$(SEARCH_LAMBDA_PACKAGE)
SEARCH_FUNCTIONS = $(SEARCH_STACK)-ingest-s3



.PHONY: $(SEARCH_FUNCTIONS)

# Run all tests
test: cfn-validate
	cd inventory-lambda && $(MAKE) test
	cd search-lambda && $(MAKE) test

deploy: package upload cfn-deploy


#
# Cloudformation Targets
#

# Validate the template
cfn-validate: $(STACK_TEMPLATE)
	aws cloudformation validate-template --region us-east-1 --template-body file://$(SEARCH_STACK_TEMPLATE) 1> /dev/null







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

