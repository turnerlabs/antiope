if [ -z $FULL_STACK_NAME ]; then
	echo "error FULL_STACK_NAME is not set"
    exit
fi

if [ -z $EDGE_NAME ]; then
	echo "error EDGE_NAME is not set"
    exit
fi

version_arn=$(aws lambda publish-version --function-name $EDGE_NAME | jq .FunctionArn | tr -d '"')

cf_id=$(aws cloudformation describe-stack-resources --stack-name $FULL_STACK_NAME --logical-resource-id CFDistribution | jq .StackResources[0].PhysicalResourceId | tr -d '"')

cf_distribution=$(aws cloudfront get-distribution-config --id $cf_id)
cf_etag=$(echo $cf_distribution | jq .ETag | tr -d '"')
cf_config=$(echo $cf_distribution | jq .DistributionConfig)

cf_version_arn=$(echo $cf_config | jq .DefaultCacheBehavior.LambdaFunctionAssociations.Items[0].LambdaFunctionARN | tr -d '"')

if [ "$version_arn" != "$cf_version_arn" ]; then
    echo "Version mismatch - Updating Cloudfront Distribution"
    temp_file=$(mktemp)
    echo $cf_config | jq --arg version_arn $version_arn '.DefaultCacheBehavior.LambdaFunctionAssociations.Items[0].LambdaFunctionARN = $version_arn' > $temp_file
    aws cloudfront update-distribution --id $cf_id --distribution-config file://$temp_file --if-match $cf_etag
    rm ${temp_file}
else
    echo "Cloudfront already running/deploying most recent L@E version"
fi
