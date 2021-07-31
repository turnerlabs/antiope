# Install Instructions

** Note: All of these examples imply you're deploying your prod environment **

## PreReq

1. Make sure you have the AWS CLI installed
1. Make sure you have a modern boto3
1. Make sure you have jq installed.
1. Create an [S3 Bucket](docs/AntiopeBucket.md) to act as the Antiope bucket. A CloudFormation template exists to do this.
    * **It is important that the bucket be created in the region you intend to run Antiope.**
    * This bucket contains all the packaged code, discovered resources and Reports.
1. You'll need [cft-deploy](https://github.com/jchrisfarris/cft-deploy) python package & scripts:
    * ```pip3 install cftdeploy```
1. Deploy a Cross Account role in all payer & child accounts you want to inventory.
    * One is provided in the `docs/cloudformation/SecurityCrossAccountRoleTemplate.yaml` CloudFormation template
1. Clone child repos
    * git clone https://github.com/WarnerMedia/antiope-aws-module.git
    * git clone https://github.com/WarnerMedia/antiope-hunt-scripts

## Antiope-Local Repo

Antiope is now designed to be deployed from a customized private git repository you keep in your own internal git server/cloud. You should follow the instructions for the [antiope-local](https://github.com/jchrisfarris/antiope-local) repo.


## Config File
Antiope deploys via SAM, Makefiles, cft-deploy and some AWS CLI commands inside the Makefile. Most of the common settings for each of the stacks is kept in a config.${env} file (where ${env} is your environment (ie dev, stage, prod)).

The config file is sourced by the makefiles to construct the stack name and to determine the S3 bucket and region Antiope will use. The file should look like this:
```bash
export MAIN_STACK_NAME=YOURCOMPANY-antiope-ENVIRONMENT
export BUCKET=YOURCOMPANY-antiope
export AWS_DEFAULT_REGION=us-east-1
export MANIFEST=Antiope-ENVIRONMENT-Manifest.yaml
export CUSTOM_PREFIX=YOURCOMPANY-Custom-Antiope
```
I recommending picking something very unique for `MAIN_STACK_NAME`. yourcompany-antiope is a good choice

## Lambda Layer
The majority of the python dependencies for the different stacks are managed via a [Lambda Layer](https://docs.aws.amazon.com/lambda/latest/dg/configuration-layers.html). There are separate Layers for AWS, GCP and Azure. To build and upload the AWS layer (which is required for everything), do the following:
```bash
make layer env=prod
```
The `make layer` command will append the Lambda Layer S3 Prefix to the config file


## Manifest Files
In addition to that config file, each Antiope Module needs a [CloudFormation "manifest" file](https://github.com/jchrisfarris/cft-deploy#user-content-manifest-files).

The [Antiope-Local](https://github.com/jchrisfarris/antiope-local) has sample manifests to use

## Deploying Antiope-Azure and Antiope-GCP

TODO

## Deploying Custom Stack

Antiope supports the idea of a Custom stack with functions that relate to your enterprise needs. You can create custom inventory lambda, or custom reports. A Custom Stack should have a custom Stepfunction which will be called by the main antiope StepFunction after all the inventory stepfunctions are run.

You can also subscribe custom functions to the Inventory Trigger topics for the AWS Accounts or AWS Organizational Payers, which will be run during the main inventory phase.

Custom Stack code should be part of your [Antiope-Local](https://github.com/jchrisfarris/antiope-local), and can be deployed via `make custom-deploy` or `make custom-promote` make targets.


## Post-Install

1. `make trigger-inventory env=prod` will trigger an immediate run of the Inventory StepFunction
2. `make disable-inventory env=prod` and `make enable-inventory env=prod` will disable or enable the CloudWatch Event that triggers the StepFunction's execution
3. Verify things look healthy in the [dashboard](https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=antiope-prod)

TODO - Log Expiration
In the aws-inventory and search-cluster directories, the `make expire-logs env=prod` command will set a 5 day retention period for the CloudWatch logs for the lambda. Otherwise the retention is indefinite.


## Other Make Targets (for development)

### Syncing data
* `make sync-resources env=prod type=<service>/<resource>` will copy down all the objects in S3 under the prefix of Resources/*service*/*resource*
* `make sync-reports env=prod` will copy down the reports

These are mostly useful for troubleshooting. `sync-resources` can be a lot of objects


