#!/bin/bash

PREFIX=$1

if [ -z $PREFIX ] ; then
	echo "Usage: $0 <table-prefix>"
	exit 1
fi

DATE=`date +%Y-%m-%d-%H%M`

TABLES=`aws dynamodb list-tables --output text | awk '{print $NF}' | grep  $PREFIX`

for t in $TABLES ; do
	BACKUPNAME="${t}-${DATE}"
	aws dynamodb create-backup --table-name $t --backup-name $BACKUPNAME
done