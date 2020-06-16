#!/bin/bash

while `/usr/bin/true` ; do
  aws s3 mb s3://warnermedia-antiope-qa
  if [ $? -eq 0 ] ; then
	exit 0
  fi
  sleep 150
done
