

# Static, not sure if needed??
PYTHON=python3
PIP=pip3

FILES=PUT Your Function Files Here

DEPENDENCIES=PUT Any Dependency Directories to Package Here

package: test clean deps zipfile

#
# Lambda function management
#

clean:
	rm -rf __pycache__ *.zip *.dist-info $(DEPENDENCIES) lib

# # Create the package Zip. Assumes all tests were done
zipfile:  $(FILES) $(DEPENDENCIES)
	cp -a $(ANTIOPE_PATH)/lib .
	zip -r $(LAMBDA_PACKAGE) $^ lib

test: $(FILES)
	for f in $^; do $(PYTHON) -m py_compile $$f; if [ $$? -ne 0 ] ; then echo "$$f FAILS" ; exit 1; fi done

deps:
	$(PIP) install -r requirements.txt -t . --upgrade
