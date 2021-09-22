# Copyright 2019-2020 Turner Broadcasting Inc. / WarnerMedia
# Copyright 2021 Chris Farris <chrisf@primeharbor.com>
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
		inventory-cw-alarm.py \
		inventory-dx.py \
		inventory-ebs-snapshot.py \
		inventory-ebs-volume.py \
		inventory-ecr.py \
		inventory-ecs.py \
		inventory-elb.py \
		inventory-eni.py \
		inventory-es.py \
		inventory-firehose.py \
		inventory-guardduty.py \
		inventory-health-report.py \
		inventory-iam.py \
		inventory-instances-sg.py \
		inventory-kms.py \
		inventory-lambdas.py \
		inventory-redshift.py \
		inventory-rds.py \
		inventory-route53.py \
		inventory-payer-costexplorer.py \
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

DEPENDENCIES=antiope bin boto3 botocore dateutil jmespath s3transfer six.py urllib3


package: test clean deps zipfile

#
# Lambda function management
#

clean:
	rm -rf __pycache__ *.zip *.dist-info *.egg-info $(DEPENDENCIES)

# # Create the package Zip. Assumes all tests were done
zipfile:  $(FILES) html_templates
	cp -a ../../../antiope-aws-module/antiope .
	zip -r $(LAMBDA_PACKAGE) $^ $(DEPENDENCIES)

test: $(FILES)
	for f in $^; do $(PYTHON) -m py_compile $$f; if [ $$? -ne 0 ] ; then echo "$$f FAILS" ; exit 1; fi done

deps:
	$(PIP) install -r requirements.txt -t . --upgrade
	$(PIP) install ../../../antiope-aws-module -t . --upgrade --no-deps


pep8: $(FILES)
	pycodestyle $^
