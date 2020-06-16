# Adding a new Inventory Resource to Antiope

## Overview

1. Add the code to the aws-inventory/lambda directory
2. Add the serverless function to CFT
2. Add the function to the Dashboard in the CFT
3. Add the filename to the FILES= list in the aws-inventory/lambda/Makefile
4. Add the function name to the FUNCTIONS= list in the aws-inventory/Makefile
5. If any special Elastic Search mapping is needed, create the mapping in search-cluster/mappings
6. Add any new resource type created to INDICES= in search-cluster/scripts/post-deploy.sh
7. Create the index(es) in ES before deploying the function (otherwise the custom or default Antiope mapping won't be present when the first document is indexed)



## Code Creation
* Filename convention is "inventory-" and the thing (or things) you're going to inventory

* Each resource should have it's own resourceType (ie "AWS::IAM::Role", "AWS::EC2::Instance" )
    * Use the AWS Config or AWS CloudFormation Resource type if available.
    * If there is no defined resource type, at least attempt to use the same convention as Config or CloudFormation for the Service (ie "IAM", "EC2")
    * refer to docs/resource_types.md and please be sure to update that file with new resource types

* Objects should be saved to the Resources/<service>/<type> directory
    * Service should be the short lowercase name used for the service in IAM Actions (ie "iam", "ec2")
    * Type should be the lowercase version of the right-most element of resourceType (ie "role", "instance")
    * The Elastic search index will be created from these elements (ie "resources_iam_role", "resources_ec2_instance")

* resourceId needs to be globally unique. This is the final part of the object key.
    * For ec2 instances (i-djfafds) and for s3 buckets this is not a problem
    * for IAM Roles or Lambda functions, the name is scoped to an AWS Account or an AWS Account and region (respectively). The ResourceId should contain the account and region if needed to disambiguate.

* Be familiar with the pydoc of antiope.aws_account.py, it contains many useful helper functions for cross account roles, etc.
    * From the antiope or lambda directory, run ```pydoc lib/account.py```

* The following elements are required for all Antiope resources
```python
resource_item = {}
resource_item['awsAccountId']                   = target_account.account_id
resource_item['awsAccountName']                 = target_account.account_name
resource_item['resourceType']                   =
resource_item['source']                         = "Antiope"
resource_item['configurationItemCaptureTime']   = str(datetime.datetime.now())
resource_item['configuration']                  =
resource_item['resourceId']                     =
resource_item['supplementaryConfiguration']     = {}
resource_item['errors']                         = {}
```

* The following elements are optional, but should adhere to this key name convention
```python
resource_item['awsRegion']                      =
resource_item['tags']                           =
resource_item['resourceName']                   =
resource_item['ARN']                            =
resource_item['resourceCreationTime']           =
```

*Building the Resource*
* The results of the describe call should go into 'configuration'.
* Any Subsequent calls for ancillary data should go into 'supplementaryConfiguration'
* If any errors are caught during the inventory gather, append them to the 'errors' dict. An example of an errors that can occur when the Antiope Audit Role doesn't have permission to describe a KMS key, or an S3 bucket policy prohibits getting certain supplementaryConfiguration elements.
* Like AWS Config Service, the tags (if returned in the describe call, or as a supplementaryConfiguration call), should be converted to a clean python dict and saved as 'tags'. The parse_tags() function takes a tagset from AWS and properly converts it.
* If the item has a Name element in the describe call, that should be the value of 'resourceName'. If not, and a Tag of 'Name' exists, that should be the 'resourceName'. Otherwise that filed should be omitted.
* If the describe call returns a value that is applicable for 'resourceCreationTime', that element should be populated. Ditto with the ARN.


*Other things to consider*
* Be sure to note which calls require pagination and which ones return all the results
* Be sure to note which resources are regional vs global, and don't iterate across regions to inventory global services
* Default memory size for a function is 128MB. If you must adjust the memory, try and leverage the pSmallLambdaSize and pLargeLambdaSize CloudFormation parameters.
* Each service is different, and AWS doesn't have standards on how their API works. Some services require you to first list all the resources, and then run a describe on each resource. Some services let you get all the data for all the resources with just a describe command. The [Boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/index.html) docs are your friend.


## CFT additions
You can easily add this block to the CFT. You want to change BucketInventoryLambdaFunctionPermission to be something unique to your function. Otherwise just update FunctionName, Description and Handler


```yaml
  BucketInventoryLambdaFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub "${pResourcePrefix}-bucket-inventory"
      Description: Inventory Buckets
      Handler: inventory-buckets.lambda_handler
      Role: !GetAtt InventoryLambdaRole.Arn
      CodeUri: ../lambda
      Events:
        AccountInventoryTrigger:
          Type: SNS
          Properties:
            Topic: !Ref TriggerAccountInventoryFunctionTopic
```

This function is run for all AWS accounts because it's subscribed to `TriggerAccountInventoryFunctionTopic`. If you have something to run just for each payer, you can subscribe it to `TriggerPayerInventoryFunctionTopic`

Dashboard additions. There are three dashboard elements that list all the Inventory functions, The following line should be added to each of the three sections (preferably just above create-account-report)
```
[ "...", "${AWS::StackName}-secrets-inventory", { "stat": "Sum", "period": 604800, "label": "secrets-inventory" } ],
```

Note the first two graphs should be period of 604800, the last should be period of 900


## Makefile updates
In order for the new file to be included in the Lambda Zip, you need to make sure it is added to the FILES= list in the aws-inventory/lambda/Makefile

In order for the new function to be supported with the ```make update``` command you must add the function name to the FUNCTIONS= list in the aws-inventory/Makefile


## Elastic Search Updates

## Deploy options

To first deploy the function, you should make sure the index with the correct mapping is created in ES first. Once the first document is indexed, you'll have to delete the index and recreate it with the proper mapping.

The first time you add a function to the index, you should run a ```make deploy```. This will both upload the lambda code and update the CloudFormation template to deploy the new lambda.

As you make changes to the lambda, you can speed up the deploy cycle by running ```make fupdate function=my-new-function-name``` in the aws-inventory director, that will just rezip the new code and manually push it to the one function. Note: if you need to modify any dependencies deployed via requirements.txt, you should run a ```make update``` instead. That will rerun the ```make deps``` and update all the functions.

If you want to disable inventory while troubleshooting the ```make disable-inventory``` command in the antiope directory will turn off the State Machine event trigger. If you need to manually trigger the step function, you can run ```make trigger-inventory```


