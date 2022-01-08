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


RESOURCEID="MasterStateMachine"

# if [ ! -x jq ] ; then
#     echo "jq not installed or not in path"
#     exit 1
# fi

STACKNAME=$1
EVENT=$2
if [ -z $STACKNAME ] ; then
    echo "Must specify STACKNAME"
    exit 1
fi

# If the user didn't pass in an event file, then get the payer list via the stack's parameters (using this ugly jq command)
if [ -z $EVENT ] ; then
    EVENT="${STACKNAME}-test-event.json" # file to save the event as
    EVENTJSON=`aws cloudformation describe-stacks --stack-name ${STACKNAME} | jq -r '.Stacks[].Parameters[]|select(.ParameterKey=="pEventJson").ParameterValue'`
    if [ -z "$EVENTJSON" ] ; then
        echo "Didn't find the payerlist in stack ${STACKNAME}. Aborting..."
        exit 1
    fi
    echo "$EVENTJSON" > $EVENT
elif [ ! -f $EVENT ] ; then
    echo "Cannot find file $EVENT. Aborting..."
    exit 1
fi

DATE=`date +%Y-%m-%d-%H-%M`
STATEMACHINE_ARN=`aws cloudformation describe-stack-resources --stack-name ${STACKNAME} --output text | grep ${RESOURCEID} | awk '{print $3}'`
if [ -z $STATEMACHINE_ARN ] ; then
    echo "Unable to find StateMachine Arn for Stack ${STACKNAME}. Aborting.."
    exit 1
fi

aws stepfunctions start-execution --state-machine-arn ${STATEMACHINE_ARN} --name "make-trigger-${DATE}" --input file://$EVENT
