

## Steps to add a new Inventory Source
1. Add the function to the FUNCTIONS in aws-inventory/Makefile
2. Add the filename to the FILES in aws-inventory/lambda/Makefile
3. Create the Lambda block in the CFT aws-inventory/cloudformation/Inventory-Template.yaml
```  SecretsManagerInventoryLambdaFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: !Sub "${AWS::StackName}-secrets-inventory"
      Description: Inventory Secrets Manager Secrets
      Handler: inventory-secrets.lambda_handler
      Runtime: python3.6
      Timeout: 300
      MemorySize: !Ref pSmallLambdaSize
      Role: !GetAtt InventoryLambdaRole.Arn
      Code:
        S3Bucket: !Ref pBucketName
        S3Key: !Sub ${pLambdaZipFile}
      Environment:
        Variables:
          ROLE_SESSION_NAME: !Ref AWS::StackName
          INVENTORY_BUCKET: !Ref pBucketName
          ACCOUNT_TABLE: !Ref AccountDBTable
          VPC_TABLE: !Ref VpcInventoryDBTable
          ROLE_NAME: !Ref pRoleName
      # Tags inherited from Stack
```
4. Add the Permission & Subscription so the function is called with all the others
```
  SecretsManagernventoryLambdaFunctionPermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !GetAtt SecretsManagerInventoryLambdaFunction.Arn
      Principal: sns.amazonaws.com
      SourceArn: !Ref TriggerAccountInventoryFunctionTopic
      Action: lambda:invokeFunction

  SecretsManagerInventoryTopicToLambdaSubscription:
    Type: AWS::SNS::Subscription
    Properties:
      Endpoint: !GetAtt [SecretsManagerInventoryLambdaFunction, Arn]
      Protocol: lambda
      TopicArn: !Ref 'TriggerAccountInventoryFunctionTopic'
```
5. Add the function name to the dashboard block of the CFT for both the Lambda Errors and Lambda invocation sections
```
[ "...", "${AWS::StackName}-secrets-inventory", { "stat": "Sum", "period": 604800, "label": "secrets-inventory" } ],
```
6. Duplicate an existing check as your template and modify.