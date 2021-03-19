# Static, not sure if needed??
PYTHON=python3
PIP=pip3


# List all of the file that belong in the Lambda zipfile package here.
FILES = waf-log-to-splunk.py \
		resourceloader.py \
		awssecret.py \
		splunkhec.py \
		awsevents.py

STATICFILES =

DEPENDENCIES  = certifi


package: test clean deps zipfile

#
# Lambda function management
#

clean:
	rm -rf __pycache__ *.zip *.dist-info $(DEPENDENCIES)

# # Create the package Zip. Assumes all tests were done
zipfile: deps $(FILES) $(DEPENDENCIES) $(STATICFILES)
	zip -r $(LAMBDA_PACKAGE) $^

test: $(FILES)
	for f in $^; do $(PYTHON) -m py_compile $$f; if [ $$? -ne 0 ] ; then echo "$$f FAILS" ; exit 1; fi done

deps:
	$(PIP) install -r requirements.txt -t . --upgrade

pep8: $(FILES)
	pycodestyle $^
