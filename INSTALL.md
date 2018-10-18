# Install Instructions

## PreReq

1. Make sure you have the AWS CLI installed
1. Make sure you have jq installed.
1. Create an S3 Bucket to act as the inventory bucket
1. You'll need the [aws_scripts repo](https://github.com/jchrisfarris/aws_scripts) and the bin and sbin directories in your path.
1. Deploy a Cross Account role in all payer & child accounts you want to inventory.
    * One is provided in the `cloudformation/SecurityCrossAccountRoleTemplate.yaml` Cloudformation template

## Install steps
1. Clone the repo
2. Pick a name for the environment. I use dev, stage and prod for development. I'll use "prod" for all examples going forward
3. Generate a cloudformation manifest file
```bash
deploy_stack.rb -g cloudformation/Inventory-Template.yaml > cloudformation/Inventory-Manifest-prod.yaml
```
4. Edit the Inventory-Manifest-prod.yaml
    1. Set the StackName
    1. pBucketName and pDeployBucket are the name of the Inventory bucket you created above
    3. pPayerAccountList is a comma seperated list of the payer account IDs for your organization
    4. Any Tags you want the stack to have can be added in the Tags Section. All tags will propagate to the Lambda Functions and DynamoDB Tables.
5. Set STACK_PREFIX in the makefile
5. Execute a make deploy to create the stack
```bash
make env=prod deploy
```
6. Trigger the inventory by hand
```bash
./bin/trigger_state_machine.sh prod
```
7. Verify things look healthy in the [dashboard](https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=antiope-prod)

## Testing & Other stuff
The Makefile has many targets for ease of development.

* `make deploy` will bundle the lambda zip file, push to S3 and create/update the cloudformation stack
* `make update` will bundle the lambda zip and update each function, bypassing Cloudformation - useful for iterative development.
* `make fupdate function=<functioname>` will bundle the lambda zip, and update only a single function - also useful for development
* `make purge` will purge the DDB Tables.
* `make clean` gets rid of the python build artifacts

These targets do part of the process
* `make test` validats the Python & CFT Syntax
* `make package` and `make upload` create the lambda zipfile and push it to S3
* In the lambda subdirectory `make deps` will pip install the requirements and bring in the library files (done prior to the lambda bundle)