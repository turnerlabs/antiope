# Install Instructions

** Note: All of these examples imply you're deploying your prod environment **

## PreReq

1. Make sure you have the AWS CLI installed
1. Make sure you have jq installed.
1. Create an S3 Bucket to act as the inventory bucket
    * **It is important that the bucket be created in the region you intend to run Antiope.**
1. You'll need cftdeploy python package & scripts:
    * ```pip3 install cftdeploy```
1. Deploy a Cross Account role in all payer & child accounts you want to inventory.
    * One is provided in the `cloudformation/SecurityCrossAccountRoleTemplate.yaml` CloudFormation template

## Config File
Antiope deploys via Makefiles, cft-deploy and some AWS CLI commands inside the Makefile. Most of the common settings for each of the stacks is kept in a config.${env} file (where ${env} is your environment (ie dev, stage, prod)).

The config file is sourced by the makefiles to construct the stack name and to determine the S3 bucket and region Antiope will use. The file should look like this:
```bash
STACK_PREFIX=                   # this is unique to your organization
BUCKET=                         # The name of the S3 bucket that Antiope will use
AWS_DEFAULT_REGION=us-west-2    # I separate my Antiope environments by region to constrain side effects with lambda concurrency issues
```
I recommending picking something very unique for `STACK_PREFIX`. yourcompany-antiope is a good choice

## Lambda Layer
The majority of the python dependencies for the different stacks are managed via a [Lambda Layer](https://docs.aws.amazon.com/lambda/latest/dg/configuration-layers.html). There are separate Layers for AWS, GCP and Azure. To build and upload the AWS layer (which is required for everything), do the following:
```bash
make layer env=prod
```
Note the output of the layer process. You need to add that to your manifest files below.

## Manifest Files
In addition to that config file, each Antiope Module needs a [CloudFormation "manifest" file](https://github.com/jchrisfarris/cft-deploy#user-content-manifest-files).

Sample Manifest files can be found in docs/sample-manifests. You can copy the samples and place them in the right directory with the correct name, or autogenerate the manifest with `make manifests env=prod` from the main Antiope directory

The Manifest files need to be tweaked for your environment.
* cognito/cloudformation/${STACK_PREFIX}-${env}-cognito-Manifest.yaml
    1. Remove the line and comments for `S3Template`, `pBucketName`, `pLambdaZipFile`, and `pVersion`. These are all managed by the makefile.
    2. Set `pCustomAPIDomain` to the URL you want the Antiope reports to show up as.

* aws-inventory/cloudformation/${STACK_PREFIX}-${env}-aws-inventory-Manifest.yaml
    1. Remove the line and comments for `S3Template`, `pBucketName`, `pLambdaZipFile`, and `pVersion`. These are all managed by the makefile.
    2. Set the `pAWSLambdaLayerPackage` from the output of the Lambda Layer step above
    4. If you want an IAM user created with permissions to the bucket, specify the username as `pIamUserName`, otherwise remove the entry or set it to `NONE`.
    4. Any Tags you want the stack to have can be added in the Tags Section. All tags will propagate to the Lambda Functions and DynamoDB Tables.
    5. In order to protect the DynamoDB tables from accidental deletion or overwrite by CloudFormation, add the following to the StackPolicy:
    ```
        - Resource:
            - LogicalResourceId/AccountDBTable
            - LogicalResourceId/VpcInventoryDBTable
            - LogicalResourceId/HistoricalBillingDataTable
            Effect: Deny
            Principal: "*"
            Action:
              - "Update:Delete"
              - "Update:Replace"
    ```

* search-cluster/cloudformation/${STACK_PREFIX}-${env}-search-cluster-Manifest.yaml
    1. `pDomainName` is the name of the Elastic Search domain to be created.
    2. Cluster Instance Types in the t2 family do not support Cluster Encryption. Your stack will fail to deploy if these two settings don't align
    3. Experience seems to be that it's best to scale `pClusterInstanceCount` out rather than making `pClusterInstanceType` larger.

## AWS Inventory Config json
Finally, the AWS Inventory needs it's config file created and pushed to S3. The file must be named `PREFIX-ENV-aws-inventory-config.json` and reside in the root of the Antiope Bucket. A sample config file can be found in `aws-inventory/config-SAMPLE.json`. This contains the list of organizational master/payer accounts to inventory in addition to any stepfunction arns the inventory StepFunction should pass off to. If you don't need to chain Step Functions right now, you can remove the `next_function` block. `make deploy` in the `aws-inventory` directory will copy the config file to S3. Copy the sample config to the proper `PREFIX-ENV-aws-inventory-config.json` filename in the aws-inventory subdirectory. It will be pushed to S3 when the stack is deployed.

## Easy install Instructions
The top-level make file lists all of the targets you can execute.

If you're looking to install everything, `make everything env=prod` will source the config.prod file and create the Cognito, AWS Inventory and Search Cluster stacks.

If you wish to install only some components of Antiope, then the following make commands will work:
```bash
make cognito-deploy env=prod
make inventory-deploy env=prod
make search-deploy env=prod
```
You can select only the ones you need.

See the GCP-INSTALL.md and Azure-INSTALL.md files for specific instructions for these cloud providers

## Post-Install

1. `make trigger-inventory env=prod` will trigger an immediate run of the Inventory StepFunction
2. `make disable-inventory env=prod` and `make enable-inventory env=prod` will disable or enable the CloudWatch Event that triggers the StepFunction's execution
3. Verify things look healthy in the [dashboard](https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=antiope-prod)

In the aws-inventory and search-cluster directories, the `make expire-logs env=prod` command will set a 5 day retention period for the CloudWatch logs for the lambda. Otherwise the retention is indefinite.


## If something goes wrong
Not all the configuration for Antiope can be done via CloudFormation. There are report template files that need to be pushed to S3. There are some AWS features that CloudFormation doesn't or cannot support. These are typically done as additional targets in the makefiles. For example, the Cognito Identity pool is given a custom login URL based on ${STACK_PREFIX}-${env}. Since these are global across AWS, it is possible this will fail due to the ${STACK_PREFIX}-${env} being in use.

The search cluster has quite a few post-install steps. One enables the Kibana auth to Cognito, another creates the bucket notification configuration so s3 put events are sent to SQS. Finally one pre-creates all the ElasticSearch mappings.

## Other Make Targets (for development)

### Syncing data
* `make sync-resources env=prod type=<service>/<resource>` will copy down all the objects in S3 under the prefix of Resources/*service*/*resource*
* `make sync-reports env=prod` will copy down the reports

These are mostly useful for troubleshooting. `sync-resources` can be a lot of objects


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










