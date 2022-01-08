# Copyright 2019-2020 Turner Broadcasting Inc. / WarnerMedia
# Copyright 2021 Chris Farris <chrisf@primeharbor.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

ifndef MAIN_STACK_NAME
	$(error MAIN_STACK_NAME is not set)
endif

ifndef BUCKET
	$(error BUCKET is not set)
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


