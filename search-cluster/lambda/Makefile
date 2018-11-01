

# Static, not sure if needed??
PYTHON=python3
PIP=pip3

FILES=ingest_s3.py

DEPENDENCIES=requests lib requests_aws4auth requests_aws4auth certifi chardet idna urllib3

package: test clean zipfile

#
# Lambda function management
#

clean:
	rm -rf __pycache__ *.zip *.dist-info HISTORY.rst bin README.rst LICENSE NOTICE bin $(DEPENDENCIES)


# # Create the package Zip. Assumes all tests were done
zipfile: deps $(FILES) $(DEPENDENCIES)
	zip -r $(LAMBDA_PACKAGE) $^

test: $(FILES)
	for f in $^; do $(PYTHON) -m py_compile $$f; if [ $$? -ne 0 ] ; then echo "$$f FAILS" ; exit 1; fi done

deps:
	$(PIP) install -r requirements.txt -t . --upgrade
	cp -a ../../lib .
