

# Static, not sure if needed??
PYTHON=python3
PIP=pip3

FILES =	get_billing_data.py \
		inventory-ami.py \
		inventory-buckets.py \
		inventory-cft.py \
		inventory-cloudfront.py \
		inventory-cloudtrail.py \
		inventory-dx.py \
		inventory-ecr.py \
		inventory-ecs.py \
		inventory-eni.py \
		inventory-es.py \
		inventory-health-report.py \
		inventory-iam.py \
		inventory-instances-sg.py \
		inventory-kms.py \
		inventory-lambdas.py \
		inventory-route53.py \
		inventory-secrets.py \
		inventory-ssm.py \
		inventory-support-cases.py \
		inventory-trusted-advisor.py \
		inventory-vpc.py \
		new_account_handler.py \
		pull_organization_data.py \
		report-accounts.py \
		report-foreign.py \
		report-vpcs.py \
		trigger_account_actions.py

DEPENDENCIES=lib

package: test clean deps zipfile

#
# Lambda function management
#

clean:
	rm -rf __pycache__ *.zip *.dist-info $(DEPENDENCIES)

# # Create the package Zip. Assumes all tests were done
zipfile:  $(FILES) $(DEPENDENCIES)
	cp -a ../../lib .
	zip -r $(LAMBDA_PACKAGE) $^

test: $(FILES)
	for f in $^; do $(PYTHON) -m py_compile $$f; if [ $$? -ne 0 ] ; then echo "$$f FAILS" ; exit 1; fi done

deps:
	$(PIP) install -r requirements.txt -t . --upgrade
	cp -a ../../lib .
