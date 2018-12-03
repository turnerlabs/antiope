# Static, not sure if needed??
PYTHON=python3

FILES=auth-at-edge.js
DEPENDENCIES=node_modules

package: clean zipfile

#
# Lambda function management
#

clean:
	rm -rf *.zip

# # Create the package Zip. Assumes all tests were done
zipfile: $(FILES) $(DEPENDENCIES)
	zip -r $(LAMBDA_PACKAGE) $^
