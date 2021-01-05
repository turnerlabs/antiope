

# Static, not sure if needed??
PYTHON=python3
PIP=pip3

FILES=ingest_sns_sqs.py ingest_sqs_direct.py

DEPENDENCIES=

package: test clean deps zipfile

#
# Lambda function management
#

clean:
	rm -rf __pycache__ *.zip *.dist-info HISTORY.rst bin README.rst LICENSE NOTICE bin $(DEPENDENCIES)


# # Create the package Zip. Assumes all tests were done
zipfile: $(FILES) $(DEPENDENCIES)
	zip -r $(LAMBDA_PACKAGE) $^

test: $(FILES)
	for f in $^; do $(PYTHON) -m py_compile $$f; if [ $$? -ne 0 ] ; then echo "$$f FAILS" ; exit 1; fi done

deps:
	$(PIP) install -r requirements.txt -t . --upgrade

pep8: $(FILES)
	pycodestyle $^
