# Making Enterprise customizations to Antiope

Antiope is designed to be a framework and starting point for your Cloud Security Inventory, Compliance and Vulnerability needs. Your organization may have have other things you need to track and the Antiope framework _should_ help support that.

## Integration Points

### Inventory Topic
There are three SNS Topic that are created by the inventory stack:

* TriggerAccountInventoryFunctionTopic: All enterprise accounts get a message published to this topic during the inventory run. You can subscribe additional inventory lambda functions to this topic and they will be inventoried during the inventory pass.
* TriggerPayerInventoryFunctionTopic: The same as the TriggerAccountInventoryFunctionTopic, but is run only for the various payers
* NewAccountNotificationTopic: When Antiope discovers a new AWS account in your organization, a message is published to this topic.
* ForeignAccountNotificationTopic: When Antiope discovers a new AWS account that is _trusted_ but not part of your organization, a message is published to this topic.

### Antiope StepFunction
At the conclusion of the Inventory StepFunctions, Antiope can pass off to another custom StepFunction. Here you can create additional reports or conduct post-inventory analysis of the results. Pass the ARN of this function to the `pDeployCustomStackStateMachineArn` parameter of the main Antiope template


### SNS Messages Published to each topic

TODO: Document these.


## Creating your own Enterprise Customization Stack

**Note:** Do not put your Enterprise stack into the main Antiope Repo. The Enterprise stack is meant to include things that probably don't need to be open-sourced.

A sample framework for a company custom stack is in `docs/sample-custom-stack`

### Deployment Order

Because the customized Lambda Functions and StepFunctions tie into the existing Antiope structure, you must first deploy Antiope. You can use cft-deploy's ability to import it's parameters from other stacks to provide the references for that structure.

1. Deploy the main Antiope
2. Create manifest in the custom repo to point to the Antiope Stacks
3. Deploy the custom stack
4. Get the StepFunction ARN from the custom stack
5. Add the StepFunction ARN to the manifest file for Antiope and re-deploy.