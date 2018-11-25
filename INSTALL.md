# Install Instructions

## PreReq

1. Make sure you have the AWS CLI installed
1. Make sure you have jq installed.
1. Create an S3 Bucket to act as the inventory bucket (example is my-antiope-inventory in this doc)
1. You'll need the [aws_scripts repo](https://github.com/jchrisfarris/aws_scripts) and the bin and sbin directories in your path to run deploy_stack.rb. There are some gem dependencies in there too.
1. Deploy a Cross Account role in all payer & child accounts you want to inventory.
    * One is provided in the `cloudformation/SecurityCrossAccountRoleTemplate.yaml` Cloudformation template


## Inventory Stack Install steps
1. Clone the repo
2. Pick a name for the environment. I use dev, stage and prod for development. I'll use "prod" for all examples going forward
2. Create a config.env
```bash
STACK_PREFIX=antiope
BUCKET=my-antiope-inventory
```
3. Generate a cloudformation manifest file.
```bash
deploy_stack.rb -g cloudformation/Inventory-Template.yaml > cloudformation/<STACK_PREFIX>-<ENVIRONMENT>-aws-inventory-Manifest.yaml
```
4. Edit the Manifest file
    1. Set the StackName to <STACK_PREFIX>-<ENVIRONMENT>-aws-inventory
    1. remove the entries for pBucketName and pDeployBucket, they are supplied by the makefile
    3. pPayerAccountList is a comma seperated list of the payer account IDs for your organization
    4. If you want an IAM user created with permissions to the bucket, specify the username as pIamUserName, otherwise remove the entry.
    4. Any Tags you want the stack to have can be added in the Tags Section. All tags will propagate to the Lambda Functions and DynamoDB Tables.
5. Execute a make deploy to create the stack
```bash
make env=prod deploy
```
6. Trigger the inventory by hand
```bash
./bin/trigger_inventory.sh prod
```
7. Verify things look healthy in the [dashboard](https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=antiope-prod)

### Testing & Other stuff
The Inventory Makefile has many targets for ease of development.

* `make deploy` will bundle the lambda zip file, push to S3 and create/update the cloudformation stack
* `make update` will bundle the lambda zip and update each function, bypassing Cloudformation - useful for iterative development.
* `make fupdate function=<functioname>` will bundle the lambda zip, and update only a single function - also useful for development
* `make purge` will purge the DDB Tables.
* `make clean` gets rid of the python build artifacts

These targets do part of the process
* `make test` validats the Python & CFT Syntax
* `make package` and `make upload` create the lambda zipfile and push it to S3
* In the lambda subdirectory `make deps` will pip install the requirements and bring in the library files (done prior to the lambda bundle)


## Deploying the ElasticSearch stack

The Search Cluster inherits some of its parameters from the Inventory stack via the deploy_stack manifest files. Copy the sample Manifest file to <STACK_PREFIX>-<ENV>-search-cluster-Manifest.yaml and edit the following to your settings.
    1. StackName should be in the form of <STACK_PREFIX>-<ENV>-search-cluster
    2. pEmailAddress will be the name of the default user created in Cognito (which is useful for authentication to Kibana)
    3. Give the search domain a name
    4. Adjust the size of the domain cluster, and number of nodes. Use something other than t2 and 1 for a production Antiope cluster.
Then execute ```make deploy env=prod``` to create the Elastic Search domain and lambda to ingest new resources from S3 into ElasticSearch.







