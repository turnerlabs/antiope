# Contributing to Antiope

* See notes on [Adding New Resources](AddingNewResources.md)
* See notes on [Creating your own enterprise customizations](Customizations.md)

### Deploying for development
The individual module Makefiles have many targets for ease of development.

* `make install` will bundle the lambda zip file, push to S3 and create/update the cloudformation stack _and_ run the post-deploy scripts
* `make deploy` will bundle the lambda zip file, push to S3 and create/update the cloudformation stack (not running the post-deploy scripts)
* `make update` will bundle the lambda zip and update each function directly, bypassing CloudFormation - useful for iterative development.
* `make fupdate function=<functioname>` will bundle the lambda zip, and update only a single function - also useful for development
* `make purge` will purge the DDB Tables.
* `make clean` gets rid of the python build artifacts

These targets do part of the process
* `make test` validates the Python & CFT Syntax
* `make package` and `make upload` create the lambda zipfile and push it to S3
* In the lambda subdirectory `make deps` will pip install the requirements and bring in the library files (done prior to the lambda bundle)

### Promoting code from lower environments
Once you've got functional code in your development environment, promotion to a QA or Prod environment is easy.
1. First make sure your cloudformation stacks are running the latest & greatest by running a `make deploy`. If you've run `make update` or `make fupdate` you won't be promoting the code that's been bundled by Cloudformation
2. Find the TemplateURL in the outputs of your CloudFormation stack. This is a pointer to the transformed nested stacks and packaged code.
3. Create a cft-deploy manifest for the new environment.
3. create a config.ENV for the new environment (where env is something like "qa" or "prod")
4. If you're moving across accounts, make sure your production account has bucket-policy access to your dev environment's `deploy-scripts` prefix
5. With environment credentials to the production account, run `make promote template=TEMPLATE_URL_FROM_STEP_2 env=prod`
6. Make sure to run the post deploy tasks if this is the first time deploying to prod. `make post-deploy env=prod`