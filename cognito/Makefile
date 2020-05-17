
include ../config.$(env)
export

# STACK_PREFIX is custom to your deployment and should be the same for all Antiope Stacks
ifndef STACK_PREFIX
	$(error STACK_PREFIX is not set)
endif

ifndef BUCKET
	$(error BUCKET is not set)
endif

ifndef COGNITO_STACK_NAME
	$(error COGNITO_STACK_NAME is not set)
endif

.PHONY: $(FUNCTIONS)

# Do everything
post-install: configure-identity-pool templates api-deploy

#
# Cloudformation Targets
#

configure-identity-pool:
	$(eval ID := $(shell aws cloudformation describe-stacks --stack-name $(COGNITO_STACK_NAME) --query 'Stacks[0].Outputs[?OutputKey==`CognitoUserPoolId`].OutputValue' --output text --region $(AWS_DEFAULT_REGION)))
	-aws --region $(AWS_DEFAULT_REGION) cognito-idp create-user-pool-domain --user-pool-id $(ID) --domain $(STACK_PREFIX)-$(env)

templates:
	aws s3 sync public s3://$(BUCKET)/public

api-deploy:
	$(eval API_ID := $(shell aws apigateway get-rest-apis --query 'items[?name==`$(COGNITO_STACK_NAME)`].id' --output text --region $(AWS_DEFAULT_REGION)))
	aws apigateway create-deployment --rest-api-id $(API_ID) --region $(AWS_DEFAULT_REGION) --stage-name "Reports"
