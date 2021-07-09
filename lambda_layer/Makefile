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

ifndef pythonver
# $(error env is not set)
    pythonver ?= python3.6
endif

ifndef BUCKET
	$(error BUCKET is not set)
endif

# ifndef version
# 	export version := $(shell date +%Y%b%d-%H%M)
# endif

export LAYER_PACKAGE=Antiope-$(env)-aws-lambda-layer-$(version).zip
export OBJECT_KEY=$(DEPLOY_PREFIX)/$(LAYER_PACKAGE)


# Static, not sure if needed??
PYTHON=python3
PIP=pip3

layer: clean deps zipfile upload

#
# Lambda function management
#

clean:
	rm -rf python *.zip

# # Create the package Zip. Assumes all tests were done
zipfile:
	zip -r $(LAYER_PACKAGE) python

deps:
	$(PIP) install -r requirements.txt -t python/lib/$(pythonver)/site-packages/ --upgrade

upload:
	aws s3 cp $(LAYER_PACKAGE) s3://$(BUCKET)/$(OBJECT_KEY)
	@echo "LAYER_URL=$(OBJECT_KEY)" >> ../../config.$(env)

pep8: $(FILES)
	pycodestyle $^
