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

ifndef BUCKET
$(error BUCKET is not set)
endif

ifndef DEPLOY_PREFIX
$(error DEPLOY_PREFIX is not set)
endif

# Create and Package the Lambda Layer, copy it to S3
layer:
	cd lambda_layer && $(MAKE) layer

# Execute Code tests to validate syntax
test:
	cd aws-inventory && $(MAKE) test
	cd search-cluster && $(MAKE) test

# Add the library dependencies into the lamda folders before cloudformation package is run
deps:
	cd aws-inventory/lambda && $(MAKE) deps

#
# Testing & Cleanup Targets
#
# Validate all the CFTs. Inventory is so large it can only be validated from S3
cft-validate:
	cft-validate -t cloudformation/antiope-Template.yaml
	cft-validate -t cloudformation/Cognito-Template.yaml
	cft-validate -t search-cluster/cloudformation/SearchCluster-Template.yaml
	@aws s3 cp aws-inventory/cloudformation/Inventory-Template.yaml s3://$(BUCKET)/$(DEPLOY_PREFIX)/validate/Inventory-Template.yaml
	aws cloudformation validate-template --template-url https://s3.amazonaws.com/$(BUCKET)/$(DEPLOY_PREFIX)/validate/Inventory-Template.yaml > /dev/null
	@aws s3 rm s3://$(BUCKET)/$(DEPLOY_PREFIX)/validate/Inventory-Template.yaml

# Clean up dev artifacts
clean:
	cd aws-inventory && $(MAKE) clean
	cd search-cluster && $(MAKE) clean
	cd lambda_layer && $(MAKE) clean

# Run pep8 style checks on lambda
pep8:
	cd aws-inventory/lambda && $(MAKE) pep8
	cd search-cluster/lambda && $(MAKE) pep8

