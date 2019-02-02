# Making Enterprise customizations to Antiope

Antiope is designed to be a framework and starting point for your Cloud Security Inventory, Compliance and Vulnerability needs. Your organization may have have other things you need to track and the Antiope framework _should_ help support that.

## Integration Points

### Inventory Topic
There are three SNS Topic that are created by the inventory stack:

* InventoryTriggerTopic: All enterprise accounts get a message published to this topic during the inventory run. You can subscribe additional inventory lambda functions to this topic and they will be inventoried during the inventory pass.
* NewAccountNotificationTopic: When Antiope discovers a new AWS account in your organization, a message is published to this topic.
* ForeignAccountNotificationTopic: When Antiope discovers a new AWS account that is _trusted_ but not part of your organization, a message is published to this topic.

### AWS StepFunction
At the conclusion of the AWS Inventory Stepfunction, Antiope can pass off to another custom StepFunction. Here you can create additional reports or conduct post-inventory analysis of the results.


### SNS Messages Published to each topic

TODO: Document these.


### StepFunction Event structure for handing off to different StepFunctions
Note: in all of the examples below, capitalized words should be substituted with the appropriate values for your organization.

The Inventory StepFunction is triggered by CloudWatch Scheduled Events and passed an `event` with the path to a config file (which is stored in the root of the Antiope Bucket). The trigger event looks like this:
```json
{
  "event_file": "PREFIX-ENV-aws-inventory-config.json"
}
```

The contents of the config file are what the Antiope Inventory stack starts with and should look something like this:
```json
{
  "payer": [
    123456789012,
    210987654321,
    567890123456
  ],
  "next_function": {
    "PREFIX-ENV-aws-inventory": "arn:aws:states:REGION:ACCOUNT_ID:stateMachine:PREFIX-ENV-COMPANY-customization"
  }
}
```

At the end of the Inventory StepFunction, the hand-off function looks to see if there is a value in next-function that matches the StepFunction currently running. If so, it will invoke that new StepFunction with the full contents of current StepFunction's `event` object. In this way, multiple StepFunctions can be chained together in some kind of StepFunction Centipede. (This mechanism is how the Scorecards will be integrated at some point down the line).


## Creating your own Enterprise Customization Stack

**Note:** Do not put your Enterprise stack into the main Antiope Repo. The Enterprise stack is meant to include things that probably don't need to be open-sourced.

A sample framework for a company custom stack is in `docs/sample-custom-stack`

### Deployment Order

Because the customized Lambda Functions and StepFunctions tie into the existing Antiope structure, you must first deploy Antiope. You can use deploy_stack's ability to import it's parameters from other stacks to provide the references for that structure.

Lastly, if you've got a add-on StepFunction you need to add that StepFunction's ARN to the `next_function` attribute in the config gile.

1. Deploy the main Antiope
2. Create manifest in the custom repo to point to the Antiope Stacks
3. Deploy the custom stack
4. Get the stepfunction arn fro the custom stack
5. Add it to the config file, push config file.