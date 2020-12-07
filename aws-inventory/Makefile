
ifndef env
# $(error env is not set)
	env ?= dev
endif

include ../config-files/config.$(env)
export

# MAIN_STACK_NAME is custom to your deployment and should be the same for all Antiope Stacks
ifndef MAIN_STACK_NAME
	$(error MAIN_STACK_NAME is not set)
endif

ifndef BUCKET
	$(error BUCKET is not set)
endif

ifndef version
	export version := $(shell date +%Y%b%d-%H%M)
endif

RESOURCE_PREFIX=$(MAIN_STACK_NAME)-aws-inventory

# Name of the Zip file with all the function code and dependencies
export LAMBDA_PACKAGE=$(RESOURCE_PREFIX)-lambda-$(version).zip

# List of all the functions deployed by this stack. Required for "make update" to work.
FUNCTIONS = $(RESOURCE_PREFIX)-pull-organization-data \
			$(RESOURCE_PREFIX)-ia2-analyzer-inventory \
			$(RESOURCE_PREFIX)-ia2-org-findings \
			$(RESOURCE_PREFIX)-ami-inventory \
			$(RESOURCE_PREFIX)-bucket-inventory \
			$(RESOURCE_PREFIX)-cloudformation-inventory \
			$(RESOURCE_PREFIX)-cloudfront-inventory \
			$(RESOURCE_PREFIX)-cloudtrail-inventory \
			$(RESOURCE_PREFIX)-client-vpn-inventory \
			$(RESOURCE_PREFIX)-dx-inventory \
			$(RESOURCE_PREFIX)-ebs-snap-inventory \
			$(RESOURCE_PREFIX)-ebs-vol-inventory \
			$(RESOURCE_PREFIX)-ecr-inventory \
			$(RESOURCE_PREFIX)-ecs-inventory \
			$(RESOURCE_PREFIX)-elb-inventory \
			$(RESOURCE_PREFIX)-eni-inventory \
			$(RESOURCE_PREFIX)-es-inventory \
			$(RESOURCE_PREFIX)-transit-gw-inventory \
			$(RESOURCE_PREFIX)-guardduty-inventory \
			$(RESOURCE_PREFIX)-health-inventory \
			$(RESOURCE_PREFIX)-iam-inventory \
			$(RESOURCE_PREFIX)-instances-sg-inventory \
			$(RESOURCE_PREFIX)-kms-inventory \
			$(RESOURCE_PREFIX)-lambdas-inventory \
			$(RESOURCE_PREFIX)-rds-inventory \
			$(RESOURCE_PREFIX)-route53-inventory \
			$(RESOURCE_PREFIX)-secrets-inventory \
			$(RESOURCE_PREFIX)-shield-inventory \
			$(RESOURCE_PREFIX)-ssm-inventory \
			$(RESOURCE_PREFIX)-sqs-inventory \
			$(RESOURCE_PREFIX)-support-inventory \
			$(RESOURCE_PREFIX)-ta-inventory \
			$(RESOURCE_PREFIX)-vpc-inventory \
			$(RESOURCE_PREFIX)-waf-inventory \
			$(RESOURCE_PREFIX)-trigger-inventory \
			$(RESOURCE_PREFIX)-get-billing-data \
			$(RESOURCE_PREFIX)-create-account-report \
			$(RESOURCE_PREFIX)-create-cred-report \
			$(RESOURCE_PREFIX)-create-foreign-account-report \
			$(RESOURCE_PREFIX)-create-vpc-report \
			$(RESOURCE_PREFIX)-worklink-inventory \
			$(RESOURCE_PREFIX)-new_account_handler

.PHONY: $(FUNCTIONS)

#
# Lambda Targets
#
clean:
	cd lambda && $(MAKE) clean

test:
	cd lambda && $(MAKE) test

package:
	cd lambda && $(MAKE) package

zipfile:
	cd lambda && $(MAKE) zipfile

# Update the Lambda Code without modifying the CF Stack
update: package $(FUNCTIONS)
	for f in $(FUNCTIONS) ; do \
	  aws lambda update-function-code --region $(AWS_DEFAULT_REGION) --function-name $$f --zip-file fileb://lambda/$(LAMBDA_PACKAGE) ; \
	done

# Update one specific function. Called as "make fupdate function=<fillinstackprefix>-aws-inventory-ecs-inventory"
fupdate: zipfile
	aws lambda update-function-code --region $(AWS_DEFAULT_REGION) --function-name $(function) --zip-file fileb://lambda/$(LAMBDA_PACKAGE) ; \

#
# Purging Targets
#
purge-tables:
	purge_ddb_table.py --table $(RESOURCE_PREFIX)-accounts --key_attribute account_id --force
	purge_ddb_table.py --table $(RESOURCE_PREFIX)-billing-data --key_attribute account_id --force
	purge_ddb_table.py --table $(RESOURCE_PREFIX)-vpc-inventory --key_attribute vpc_id --force

purge-logs:
	for f in $(FUNCTIONS) ; do \
	  aws logs delete-log-group --log-group-name /aws/lambda/$$f ; \
	done

#
# Post Install Targets
#

post-deploy: expire-logs

expire-logs:
	for f in $(FUNCTIONS) ; do \
	  aws logs put-retention-policy --log-group-name /aws/lambda/$$f --retention-in-days 5 ; \
	done
