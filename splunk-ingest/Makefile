

ifndef env
# $(error env is not set)
	env ?= dev
endif

include ../config-files/config.$(env)
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

# Specific to this stack
RESOURCE_PREFIX=$(MAIN_STACK_NAME)-search-cluster

# Name of the Zip file with all the function code and dependencies
export LAMBDA_PACKAGE ?= $(RESOURCE_PREFIX)-lambda-$(version).zip

# List of all the functions deployed by this stack. Required for "make update" to work.
FUNCTIONS = $(RESOURCE_PREFIX)-ingest-s3

.PHONY: $(FUNCTIONS)

post-deploy:
	./scripts/post-deploy.sh

#
# Lambda Targets
#
test:
	cd lambda && $(MAKE) test

clean:
	cd lambda && $(MAKE) clean
	cd scripts && $(MAKE) clean
	rm -f notification_template-$(MAIN_STACK_NAME).json

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
# House Cleaning Functions (for the Purge)
#
purge-logs:
	for f in $(FUNCTIONS) ; do \
	  aws --region $(AWS_DEFAULT_REGION) logs delete-log-group --log-group-name /aws/lambda/$$f ; \
	done


