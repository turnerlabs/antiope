
include ../config-files/config.$(env)
export

ifndef MAIN_STACK_NAME
$(error MAIN_STACK_NAME is not set)
endif

ifndef BUCKET
$(error BUCKET is not set)
endif

.PHONY: $(FUNCTIONS)

# Do everything
post-deploy:
	./post-deploy.sh

#
# Cloudformation Targets
#



templates:
	aws s3 sync public s3://$(BUCKET)/public

api-deploy:
	$(eval API_ID := $(shell aws apigateway get-rest-apis --query 'items[?name==`$(COGNITO_STACK_NAME)`].id' --output text --region $(AWS_DEFAULT_REGION)))
	aws apigateway create-deployment --rest-api-id $(API_ID) --region $(AWS_DEFAULT_REGION) --stage-name "Reports"
