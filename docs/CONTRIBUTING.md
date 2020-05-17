# Contributing to Antiope

### Deploying for development
The individual module Makefiles have many targets for ease of development.

* `make deploy` will bundle the lambda zip file, push to S3 and create/update the cloudformation stack
* `make update` will bundle the lambda zip and update each function directly, bypassing CloudFormation - useful for iterative development.
* `make fupdate function=<functioname>` will bundle the lambda zip, and update only a single function - also useful for development
* `make purge` will purge the DDB Tables.
* `make clean` gets rid of the python build artifacts

These targets do part of the process
* `make test` validates the Python & CFT Syntax
* `make package` and `make upload` create the lambda zipfile and push it to S3
* In the lambda subdirectory `make deps` will pip install the requirements and bring in the library files (done prior to the lambda bundle)