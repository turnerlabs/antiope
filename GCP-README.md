# Deploy Instructions for GCP

## Prerequsites

1. Create a AWS Secrets Manager Secret



### Secrets Manager
```bash
. config.PROD
aws secretsmanager create-secret --name ${STACK_PREFIX}-GCP-Credentials --region ${AWS_DEFAULT_REGION} \
            --description "Provide GCP Inventory Credentails for Antiope" \
            --secret-string file://path-to-mycreds.json
````

The Arn returned by that command should be added as pGCPServiceSecretArn to the Manifest file.