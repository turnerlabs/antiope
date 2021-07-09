#!/bin/bash

for service in `aws s3 ls s3://${BUCKET}/Resources/ | awk '{print $2}' ` ; do
	for type in `aws s3 ls s3://${BUCKET}/Resources/$service | awk '{print $2}' ` ; do
		echo "resources_${service}_$type" | sed s/\\///g
	done
done