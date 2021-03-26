# Managing the Antiope Bucket


## Creating a New Antiope Bucket

To create a fresh antiope bucket, leverage the CFT in [cloudformation/antiope-bucket-Template.yaml](../cloudformation/antiope-bucket-Template.yaml).

Steps to deploy:
1. Generate a manifest:
```bash
cft-generate-manifest -m config-files/antiope-bucket-Manifest.yaml -t cloudformation/antiope-bucket-Template.yaml
```
2. Edit the `config-files/antiope-bucket-Manifest.yaml` and set the stackname and pBucketName
3. Deploy the CloudFormation Stack with:
```bash
cft-deploy -m config-files/antiope-bucket-Manifest.yaml
```

Now you can proceed to deploy the rest of Antiope

## Importing an existing Antiope Bucket into Cloudformation

If for whatever reason, you have an existing Antiope bucket you wish to use, you can use CloudFormation import to import the existing Antiope Bucket into CloudFormation, then update the bucket stack to include the other resources.

CloudFormation import has some significant limitations. Not all resources _can_ be imported, and all resources in a template _must_ be imported. To work around these limitations, there is a barebones CFT that can be used to import the existing bucket into CloudFormation. Once imported, the stack can be updated to use the main template. The steps to import an existing bucket are as follows:

1. Create an import change set:
```bash
aws cloudformation create-change-set --output text \
	--stack-name antiope-bucket \
	--change-set-name bucket-import \
	--parameters ParameterKey=pBucketName,ParameterValue=REPLACE_WITH_YOUR_BUCKET_NAME \
	--template-body file://cloudformation/antiope-bucket-ImportTemplate.yaml \
	--change-set-type IMPORT \
	--resources-to-import ResourceType=AWS::S3::Bucket,LogicalResourceId=AntiopeBucket,ResourceIdentifier={BucketName=REPLACE_WITH_YOUR_BUCKET_NAME}
```
2. Review the change set
```bash
aws cloudformation describe-change-set --change-set-name bucket-import --stack-name antiope-bucket
```
3. Execute the change set
```bash
aws cloudformation execute-change-set --change-set-name bucket-import --stack-name antiope-bucket
```
4. Validate the new stack is in `IMPORT_COMPLETE` state
5. Now update the new stack with the full-featured template. First Generate a manifest:
```bash
cft-generate-manifest -m config-files/antiope-bucket-Manifest.yaml -t cloudformation/antiope-bucket-Template.yaml
```
6. Edit the `config-files/antiope-bucket-Manifest.yaml` and set the stackname and pBucketName to the values used for the import
7. Deploy the CloudFormation Stack with:
```bash
cft-deploy -m config-files/antiope-bucket-Manifest.yaml --force
```