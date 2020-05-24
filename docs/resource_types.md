# Antiope Resource Type Registry

In order to eventually support either Lambda or Config Service collection of data, I'm aligning the Resource Type values for both of methods. In general these also look to map to what the [resource type in CloudFormation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-template-resource-type-ref.html) is.

## Config Service Resource Types

* AWS::ACM::Certificate (not yet inventoried by Antiope)
* AWS::AutoScaling::AutoScalingGroup (not yet inventoried by Antiope)
* AWS::AutoScaling::LaunchConfiguration (not yet inventoried by Antiope)
* AWS::CloudFormation::Stack
* AWS::CloudFront::Distribution
* AWS::CloudTrail::Trail
* AWS::CloudWatch::Alarm (not yet inventoried by Antiope)
* AWS::CodeBuild::Project (not yet inventoried by Antiope)
* AWS::CodePipeline::Pipeline (not yet inventoried by Antiope)
* AWS::Config::ResourceCompliance (not yet inventoried by Antiope)
* AWS::DynamoDB::Table (not yet inventoried by Antiope)
* AWS::EC2::EIP
* AWS::EC2::Instance
* AWS::EC2::InternetGateway (not yet inventoried by Antiope)
* AWS::EC2::NetworkAcl (not yet inventoried by Antiope)
* AWS::EC2::NetworkInterface
* AWS::EC2::RouteTable (not yet inventoried by Antiope)
* AWS::EC2::SecurityGroup
* AWS::EC2::Subnet (not yet inventoried by Antiope)
* AWS::EC2::VPC
* AWS::EC2::VPNGateway
* AWS::EC2::Volume
* AWS::ElasticBeanstalk::Application (not yet inventoried by Antiope)
* AWS::ElasticBeanstalk::ApplicationVersion (not yet inventoried by Antiope)
* AWS::ElasticBeanstalk::Environment (not yet inventoried by Antiope)
* AWS::ElasticLoadBalancing::LoadBalancer
* AWS::ElasticLoadBalancingV2::LoadBalancer
* AWS::IAM::Group (not yet inventoried by Antiope)
* AWS::IAM::Policy (not yet inventoried by Antiope)
* AWS::IAM::Role
* AWS::IAM::User
* AWS::Lambda::Function
* AWS::RDS::DBInstance (not yet inventoried by Antiope)
* AWS::RDS::DBSecurityGroup (not yet inventoried by Antiope)
* AWS::RDS::DBSnapshot (not yet inventoried by Antiope)
* AWS::RDS::DBSubnetGroup (not yet inventoried by Antiope)
* AWS::S3::Bucket


## Antiope Custom Resource Types (not supported by Config Service)

* AWS::ECR::Repository
* AWS::ECS::Cluster
* AWS::ECS::Task
* AWS::KMS::Key
* AWS::Route53::Domain
* AWS::Route53::HostedZone
* AWS::Elasticsearch::Domain

