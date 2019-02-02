#!/bin/bash

RESOURCEID="InventoryProcessStateMachine"

STACKNAME=$1
EVENT=$2
if [ -z $STACKNAME ] ; then
    echo "Must specify STACKNAME"
    exit 1
fi

# If the user didn't pass in an event file, then get the payer list via the stack's parameters (using this ugly jq command)
if [ -z $EVENT ] ; then
    EVENT="${STACKNAME}-test-event.json" # file to save the event as
    # PAYERLIST=`aws cloudformation describe-stacks --stack-name ${STACKNAME} | jq -r '.Stacks[].Parameters[]|select(.ParameterKey=="pPayerAccountList").ParameterValue'`
    # if [ -z "$PAYERLIST" ] ; then
    #     echo "Didn't find the payerlist in stack ${STACKNAME}. Aborting..."
    #     exit 1
    # fi
    echo "{\"event_file\": \"${STACKNAME}-config.json\" }" > $EVENT
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
