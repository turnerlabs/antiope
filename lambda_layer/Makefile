
ifndef pythonver
# $(error env is not set)
    pythonver ?= python3.6
endif

ifndef env
# $(error env is not set)
	env ?= dev
endif

include ../config-files/config.$(env)
export


ifndef BUCKET
	$(error BUCKET is not set)
endif

ifndef version
	export version := $(shell date +%Y%b%d-%H%M)
endif

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
	$(PIP) install -r requirements.txt -t python/lib/python3.6/site-packages/ --upgrade

upload:
	aws s3 cp $(LAYER_PACKAGE) s3://$(BUCKET)/$(OBJECT_KEY)
	@echo "LAYER_URL=$(OBJECT_KEY)" >> ../config.$(env)

pep8: $(FILES)
	pycodestyle $^
