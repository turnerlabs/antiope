cf_id=$(aws cloudformation describe-stack-resources --stack-name turner-antiope-dev-auth --logical-resource-id CFDistribution | jq .StackResources[0].PhysicalResourceId | tr -d '"')

domain_name=$(aws cloudfront get-distribution-config --id $cf_id | jq .DistributionConfig.Origins.Items[0].DomainName | tr -d '"')

bucket_name=$(echo $domain_name | awk -F\. '{print $(NF-3)}')


resource_name=$(aws cloudfront get-distribution-config --id $cf_id | jq .DistributionConfig.CacheBehaviors.Items[0].PathPattern | tr -d '"')

aws s3 cp html/index.html "s3://${bucket_name}/${resource_name}"
