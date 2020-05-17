# Install Instructions

** Note: All of these examples imply you're deploying your prod environment **

## PreReq

1. Make sure you have the AWS CLI installed
1. Make sure you have a modern boto3
FIXME 1. Make sure you have jq installed.
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
STACK_PREFIX=test
BUCKET=test-antiope1
AWS_DEFAULT_REGION=us-east-1
MANIFEST=${STACK_PREFIX}-Manifest.yaml
```
I recommending picking something very unique for `STACK_PREFIX`. yourcompany-antiope is a good choice

## Lambda Layer
The majority of the python dependencies for the different stacks are managed via a [Lambda Layer](https://docs.aws.amazon.com/lambda/latest/dg/configuration-layers.html). There are separate Layers for AWS, GCP and Azure. To build and upload the AWS layer (which is required for everything), do the following:
```bash
make layer env=prod
```
The `make layer` command will append the Lambda Layer S3 Prefix to the config file


## Manifest Files
In addition to that config file, each Antiope Module needs a [CloudFormation "manifest" file](https://github.com/jchrisfarris/cft-deploy#user-content-manifest-files).

A Sample Manifest can be found in docs/sample-manifests. You can copy the sample and place them in the root directory with the correct name (defined in your config file).

TODO - Params
TODO - event json

## Easy install Instructions
The top-level make file lists all of the targets you can execute.

If you're looking to install everything, `make deploy env=prod` will source the config.prod file and create the Cognito, AWS Inventory and Search Cluster stacks (if configured to do so).

Post instal
cognito - make post-install (passing in FULL_STACK_NAME)
aws-inventory make post-deploy -


## Deploying Antiope-Azure and Antiope-GCP

TODO

## Deploying Custom Stack

TODO


## Post-Install

1. `make trigger-inventory env=prod` will trigger an immediate run of the Inventory StepFunction
2. `make disable-inventory env=prod` and `make enable-inventory env=prod` will disable or enable the CloudWatch Event that triggers the StepFunction's execution
3. Verify things look healthy in the [dashboard](https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=antiope-prod)

TODO - Log Expiration
In the aws-inventory and search-cluster directories, the `make expire-logs env=prod` command will set a 5 day retention period for the CloudWatch logs for the lambda. Otherwise the retention is indefinite.


## If something goes wrong
Not all the configuration for Antiope can be done via CloudFormation. There are report template files that need to be pushed to S3. There are some AWS features that CloudFormation doesn't or cannot support. These are typically done as additional targets in the makefiles. For example, the Cognito Identity pool is given a custom login URL based on ${STACK_PREFIX}-${env}. Since these are global across AWS, it is possible this will fail due to the ${STACK_PREFIX}-${env} being in use.

The search cluster has quite a few post-install steps. One enables the Kibana auth to Cognito, another creates the bucket notification configuration so s3 put events are sent to SQS. Finally one pre-creates all the ElasticSearch mappings.

## Other Make Targets (for development)

### Syncing data
* `make sync-resources env=prod type=<service>/<resource>` will copy down all the objects in S3 under the prefix of Resources/*service*/*resource*
* `make sync-reports env=prod` will copy down the reports

These are mostly useful for troubleshooting. `sync-resources` can be a lot of objects













