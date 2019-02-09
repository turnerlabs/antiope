

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

export LAYER_PACKAGE=Antiope-$(env)-aws_lambda_layer-$(version).zip
export OBJECT_KEY=deploy-packages/$(LAYER_PACKAGE)


# Static, not sure if needed??
PYTHON=python3
PIP=pip3

DEPENDENCIES=yaml semver.py mako markupsafe bin boto3 botocore jmespath dateutil s3transfer six.py urllib3

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
	$(PIP) install -r requirements.txt -t python/lib/python3.6/site-packages/ --upgrade

upload:
	aws s3 cp $(LAYER_PACKAGE) s3://$(BUCKET)/$(OBJECT_KEY)
	echo "Add $(OBJECT_KEY) as the aws_lambda_layer"
