# AWS Config Service Notes

## Common Resource elements

ReMapped
* last_updated -> configurationItemCaptureTime
* account_id -> awsAccountId
* resource_type -> resourceType
* region -> awsRegion
* API Results -> configuration
* tags are processed into tags
* Other things are in supplementaryConfiguration

New:
* resourceId
* resourceName
* ARN
* resourceCreationTime
* source (Config or Antiope)


### Required:

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

### Optional

```python
resource_item['awsRegion']                      =
resource_item['tags']                           =
resource_item['resourceName']                   =
resource_item['ARN']                            =
resource_item['resourceCreationTime']           =
```



## Config Object types

* ConfigHistory - occurs when a change happens
* ConfigSnapshot - Every six hours or when prompted via the `aws configservice deliver-config-snapshot --delivery-channel-name default` command


## Config Supported Resources
* AWS::ACM::Certificate
* AWS::AutoScaling::AutoScalingGroup
* AWS::AutoScaling::LaunchConfiguration
* AWS::CloudFormation::Stack
* AWS::CloudFront::Distribution
* AWS::CloudTrail::Trail
* AWS::CloudWatch::Alarm
* AWS::CodeBuild::Project
* AWS::CodePipeline::Pipeline
* AWS::Config::ResourceCompliance
* AWS::DynamoDB::Table
* AWS::EC2::EIP
* AWS::EC2::Instance
* AWS::EC2::InternetGateway
* AWS::EC2::NetworkAcl
* AWS::EC2::NetworkInterface
* AWS::EC2::RouteTable
* AWS::EC2::SecurityGroup
* AWS::EC2::Subnet
* AWS::EC2::VPC
* AWS::EC2::VPNGateway
* AWS::EC2::Volume
* AWS::ElasticBeanstalk::Application
* AWS::ElasticBeanstalk::ApplicationVersion
* AWS::ElasticBeanstalk::Environment
* AWS::ElasticLoadBalancing::LoadBalancer
* AWS::ElasticLoadBalancingV2::LoadBalancer
* AWS::IAM::Group
* AWS::IAM::Policy
* AWS::IAM::Role
* AWS::IAM::User
* AWS::Lambda::Function
* AWS::RDS::DBInstance
* AWS::RDS::DBSecurityGroup
* AWS::RDS::DBSnapshot
* AWS::RDS::DBSubnetGroup
* AWS::S3::Bucket

## Resources I support that Config doesnt
* Secrets Manager
* ECR
* ECS Clusters & Tasks
* ElasticSearch
* Health Report
* KMS
* Route 53 Zones & Domains


## SNS Message
```json
New State and Change Record:
----------------------------
{
  "configurationItemDiff": {
    "changedProperties": {},
    "changeType": "CREATE"
  },
  "configurationItem": {
    "relatedEvents": [],
    "relationships": [
      {
        "resourceId": "i-0ce70dxxxxxxxx",
        "resourceName": null,
        "resourceType": "AWS::EC2::Instance",
        "name": "Is attached to Instance"
      }
    ],
    "configuration": {
      "attachments": [
        {
          "attachTime": "2018-12-16T12:41:57.000Z",
          "device": "/dev/xvda",
          "instanceId": "i-0ce70dxxxxxxxx",
          "state": "attached",
          "volumeId": "vol-004bcxxxxxxx",
          "deleteOnTermination": true
        }
      ],
      "availabilityZone": "us-east-1c",
      "createTime": "2018-12-16T12:41:57.351Z",
      "encrypted": false,
      "kmsKeyId": null,
      "size": 8,
      "snapshotId": "snap-0a0b8xxxxxxxxx",
      "state": "in-use",
      "volumeId": "vol-004bcxxxxxxx",
      "iops": 100,
      "tags": [],
      "volumeType": "gp2"
    },
    "supplementaryConfiguration": {},
    "tags": {},
    "configurationItemVersion": "1.3",
    "configurationItemCaptureTime": "2018-12-16T12:44:50.026Z",
    "configurationStateId": 56789123456,
    "awsAccountId": "123456789012",
    "configurationItemStatus": "ResourceDiscovered",
    "resourceType": "AWS::EC2::Volume",
    "resourceId": "vol-004bcxxxxxxx",
    "resourceName": null,
    "ARN": "arn:aws:ec2:us-east-1:123456789012:volume/vol-004bcxxxxxxx",
    "awsRegion": "us-east-1",
    "availabilityZone": "us-east-1c",
    "configurationStateMd5Hash": "",
    "resourceCreationTime": "2018-12-16T12:41:57.351Z"
  },
  "notificationCreationTime": "2018-12-16T12:44:50.954Z",
  "messageType": "ConfigurationItemChangeNotification",
  "recordVersion": "1.3"
}

Config History Delivery
--------------------------
{
  "s3ObjectKey": "AWSLogs/123456789012/Config/us-east-1/2018/12/16/ConfigHistory/123456789012_Config_us-east-1_ConfigHistory_AWS::RDS::DBInstance_20181216T101127Z_20181216T101127Z_1.json.gz",
  "s3Bucket": "mybucketname",
  "notificationCreationTime": "2018-12-16T11:07:14.446Z",
  "messageType": "ConfigurationHistoryDeliveryCompleted",
  "recordVersion": "1.1"
}

Config Snapshot Delivery
-------------------------
{
  "configSnapshotId": "3e46b911-99e6-4205-aba8-5739f7c37680",
  "s3ObjectKey": "AWSLogs/123456789012/Config/us-east-1/2018/12/16/ConfigSnapshot/123456789012_Config_us-east-1_ConfigSnapshot_20181216T105522Z_3e46b911-99e6-4205-aba8-5739f7c37680.json.gz",
  "s3Bucket": "mybucketname",
  "notificationCreationTime": "2018-12-16T10:55:22.830Z",
  "messageType": "ConfigurationSnapshotDeliveryCompleted",
  "recordVersion": "1.1"
}

```