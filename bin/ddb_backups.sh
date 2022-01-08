#!/bin/bash

# Copyright 2019-2020 Turner Broadcasting Inc. / WarnerMedia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


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