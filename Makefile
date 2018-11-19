
include config.env
export

ifndef STACK_PREFIX
$(error STACK_PREFIX is not set)
endif

ifndef BUCKET
$(error BUCKET is not set)
endif


cognito-deploy:
	cd cognito && $(MAKE) deploy

inventory-deploy:
	cd aws-inventory && $(MAKE) deploy

inventory-update:
	cd aws-inventory && $(MAKE) update

search-deploy:
	cd search-cluster && $(MAKE) deploy

search-update:
	cd search-clustery && $(MAKE) update

clean:
	cd aws-inventory && $(MAKE) clean
	cd search-cluster && $(MAKE) clean
	cd cognito && $(MAKE) clean

