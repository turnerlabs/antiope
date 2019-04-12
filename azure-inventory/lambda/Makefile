

# Static, not sure if needed??
PYTHON=python3
PIP=pip3

FILES=pull_organization_data.py pull_vm_data.py pull_ip_data.py report-subscriptions.py pull_storage_data.py pull_app_service_data.py

DEPENDENCIES=azure_lib  adal asn1crypto azure certifi cffi chardet cryptography dateutil doc idna isodate jwt msrest msrestazure oauthlib pycparser requests requests_oauthlib samples six.py tests urllib3
DEPENDENCY_CRUD=bin _cffi_backend.cpython-37m-darwin.so

package: test clean zipfile

#
# Lambda function management
#

clean:
	rm -rf __pycache__ *.zip *.dist-info $(DEPENDENCIES) $(DEPENDENCY_CRUD)

# # Create the package Zip. Assumes all tests were done
zipfile: deps $(FILES) $(DEPENDENCIES)
	zip -r $(LAMBDA_PACKAGE) $^

test: $(FILES)
	for f in $^; do $(PYTHON) -m py_compile $$f; if [ $$? -ne 0 ] ; then echo "$$f FAILS" ; exit 1; fi done

deps:
	$(PIP) install -r requirements.txt -t . --upgrade
	cp -a ../azure_lib .
