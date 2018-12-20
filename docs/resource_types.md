# Antiope Resource Type Registry

In order to eventually support either Lambda or Config Service collection of data, I'm aligning the Resource Type values for both of methods. In general these also look to map to what the [resource type in CloudFormation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-template-resource-type-ref.html) is.

## Config Service Resource Types

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


## Antiope Custom Resource Types (not supported by Config Service)

* AWS::ECR::Repository
* AWS::ECS::Cluster
* AWS::ECS::Task
* AWS::KMS::Key
* AWS::Route53::Domain
* AWS::Route53::HostedZone
* AWS::Elasticsearch::Domain

