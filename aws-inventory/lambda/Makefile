

# Static, not sure if needed??
PYTHON=python3
PIP=pip3

FILES =	common.py\
		get_billing_data.py \
		inventory-accessanalyzer-analyzers.py \
		inventory-accessanalyzer-findings.py \
		inventory-ami.py \
		inventory-buckets.py \
		inventory-cft.py \
		inventory-cloudfront.py \
		inventory-cloudtrail.py \
		inventory-client-vpn.py \
		inventory-dx.py \
		inventory-ebs-snapshot.py \
		inventory-ebs-volume.py \
		inventory-ecr.py \
		inventory-ecs.py \
		inventory-elb.py \
		inventory-eni.py \
		inventory-es.py \
		inventory-guardduty.py \
		inventory-health-report.py \
		inventory-iam.py \
		inventory-instances-sg.py \
		inventory-kms.py \
		inventory-lambdas.py \
		inventory-redshift.py \
		inventory-rds.py \
		inventory-route53.py \
		inventory-sagemaker.py \
		inventory-secrets.py \
		inventory-shield.py \
		inventory-ssm.py \
		inventory-support-cases.py \
		inventory-trusted-advisor.py \
		inventory-vpc.py \
		inventory-transit-gateway.py \
		inventory-waf.py \
		inventory-worklink.py \
		new_account_handler.py \
		pull_organization_data.py \
		report-accounts.py \
		report-foreign.py \
		report-unified-credential-report.py \
		report-vpcs.py \
		trigger_account_actions.py

DEPENDENCIES=antiope

package: test clean deps zipfile

#
# Lambda function management
#

clean:
	rm -rf __pycache__ *.zip *.dist-info $(DEPENDENCIES)

# # Create the package Zip. Assumes all tests were done
zipfile:  $(FILES) html_templates
	cp -a ../../antiope-aws-module/antiope .
	zip -r $(LAMBDA_PACKAGE) $^ $(DEPENDENCIES)

test: $(FILES)
	for f in $^; do $(PYTHON) -m py_compile $$f; if [ $$? -ne 0 ] ; then echo "$$f FAILS" ; exit 1; fi done

deps:
	$(PIP) install -r requirements.txt -t . --upgrade
	cp -a ../../antiope-aws-module/antiope .


pep8: $(FILES)
	pycodestyle $^
