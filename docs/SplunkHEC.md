# Adding support to send Antiope events to Splunk via HEC

Antiope supports the ability to push new resources into Splunk by way of the HTTP Event Collector. In order to do this, an SNS topic is created on the S3 bucket and an SQS Queue is subscribed to that Topic. Events on the SQS Queue consist of Object Put notifications for events written to the Antiope Bucket under Resources/.

A Lambda is invoked from these messages to read the S3 object and push to HEC. The Lambda requires an AWS Secrets Manager secret to exist with the HEC endpoint & token.

Since the S3 bucket writes to an SNS Topic, this design also supports the Antiope ElasticSearch cluster.


## Installation

1. Make sure the S3 bucket is deployed via the [Antiope Bucket Template](AntiopeBucket.md). Instructions for importing an existing bucket are also in that ReadMe file.
2. Update the main Antiope Manifest to source the SNS Topic created by the Antiope Bucket stack
```yaml
###########
# These stacks are needed by the SourcedParameters section
###########
DependentStacks:
   AntiopeBucket: antiope-bucket

###########
# Parameters that come from other deployed stacks.
# Valid Sections are Resources, Outputs Parameters
#
# Hint. Get your list of resources this way:
# aws cloudformation describe-stack-resources --stack-name stack_name_for_other_stack --output text
SourcedParameters:

  # SNS Topic from the Antiope Bucket Stack.
  pS3EventNotificationTopicArn: AntiopeBucket.Outputs.ResourceNotificationTopicArn
```
3. Install or update Antiope with `make deploy env=PROD`. This will reconfigure the search cluster to use SNS if it's enabled.
4. Create a AWS Secrets Manager Secret with the format of:
```json
{
  "HECEndpoint": "https://YOUR-SPLUNK-HEC-HOSTNAME/services/collector/event",
  "HECToken": "THIS-IS-SECRET"
}
```
5. Generate Manifest for the Splunk HEC Cluster
```bash
cft-generate-manifest -m config-files/antiope-splunk-Manifest.yaml -t cloudformation/SplunkHEC-Template.yaml
```
6. Edit the Manifest file and set the pSplunkHECSecret name and adjust the alarm threshold
7. Move the `pBucketName`, `pS3EventNotificationTopicArn`, and `pAWSInventoryLambdaLayer` entries from Parameters to SourcedParameters, and set them to the values below. Also set the DependentStacks for `Bucket` and `Antiope` to the CloudFormation stacknames you're using. The `DependentStacks` and `SourceParameters` should look like:
```yaml
###########
# These stacks are needed by the SourcedParameters section
###########
DependentStacks:
   Bucket: antiope-bucket
   Antiope: antiope

###########
# Parameters that come from other deployed stacks.
# Valid Sections are Resources, Outputs Parameters
#
# Hint. Get your list of resources this way:
# aws cloudformation describe-stack-resources --stack-name stack_name_for_other_stack --output text
SourcedParameters:

  # Name of the Antiope Bucket
  pBucketName: Bucket.Outputs.Bucket

  # SNS Topic for the Splunk Ingest SQS Queue to subscribe to.
  pS3EventNotificationTopicArn: Bucket.Outputs.ResourceNotificationTopicArn

  # ARN Antiope AWS Lambda Layer
  pAWSInventoryLambdaLayer: Antiope.Resources.AWSInventoryLambdaLayer
```
8. Deploy stack to send all Resources written to the S3 bucket to Splunk
```bash
cft-deploy -m config-files/antiope-splunk-Manifest.yaml
```