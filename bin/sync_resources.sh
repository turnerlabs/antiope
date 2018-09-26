#!/bin/bash


BUCKET=$1
if [ -z $BUCKET ] ; then
    echo "Must specify bucket name"
    exit 1
fi


aws s3 sync s3://$BUCKET/Resources/ Resources

open Resources