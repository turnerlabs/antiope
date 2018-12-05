FILES=auth-at-edge.js
DEPENDENCIES=node_modules

package: clean build zipfile

#
# Lambda function management
#

clean:
	rm -rf *.zip node_modules

build:
	npm install

# # Create the package Zip. Assumes all tests were done
zipfile: $(FILES) $(DEPENDENCIES)
	zip -r $(LAMBDA_PACKAGE) $^
