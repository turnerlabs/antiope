

# Static, not sure if needed??
PYTHON=python3
PIP=pip3

DEPENDENCIES=requests lib requests_aws4auth requests_aws4auth certifi chardet idna urllib3 elasticsearch elasticsearch5

#
# Lambda function management
#

clean:
	rm -rf __pycache__ *.zip *.dist-info HISTORY.rst bin README.rst LICENSE NOTICE bin $(DEPENDENCIES)

test: $(FILES)
	for f in $^; do $(PYTHON) -m py_compile $$f; if [ $$? -ne 0 ] ; then echo "$$f FAILS" ; exit 1; fi done

deps:
	$(PIP) install -r requirements.txt -t . --upgrade
