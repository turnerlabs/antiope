

# Static, not sure if needed??
PYTHON=python3
PIP=pip3

FILES=pull_organization_data.py get_billing_data.py inventory-instances-sg.py inventory-health-report.py inventory-eni.py inventory-vpc.py \
		inventory-route53.py inventory-buckets.py inventory-iam.py inventory-ecs.py report-accounts.py new_account_handler.py \
		inventory-cloudtrail.py inventory-es.py inventory-secrets.py inventory-ecr.py inventory-lambdas.py

DEPENDENCIES=yaml semver.py lib

package: test clean zipfile

#
# Lambda function management
#

clean:
	rm -rf __pycache__ *.zip *.dist-info $(DEPENDENCIES)

# # Create the package Zip. Assumes all tests were done
zipfile: deps $(FILES) $(DEPENDENCIES)
	zip -r $(LAMBDA_PACKAGE) $^

test: $(FILES)
	for f in $^; do $(PYTHON) -m py_compile $$f; if [ $$? -ne 0 ] ; then echo "$$f FAILS" ; exit 1; fi done

deps:
	$(PIP) install -r requirements.txt -t . --upgrade
	cp -a ../../lib .
