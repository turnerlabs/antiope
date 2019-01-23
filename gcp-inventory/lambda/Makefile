

# Static, not sure if needed??
PYTHON=python3
PIP=pip3

FILES=pull_organization_data.py report-projects.py new_project_handler.py

DEPENDENCIES=gcp_lib google googleapiclient httplib2 oauth2client pyasn1 pyasn1_modules rsa uritemplate
DEPENDENCY_CRUD=google_auth-1.6.2-py3.7-nspkg.pth apiclient google_auth_httplib2.py bin cachetools six.py

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
	cp -a ../gcp_lib .
