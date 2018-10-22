
include config.env
export


ifndef STACK_PREFIX
$(error STACK_PREFIX is not set)
endif

ifndef BUCKET
$(error BUCKET is not set)
endif



inventory-deploy:
	cd aws-inventory && $(MAKE) deploy

inventory-update:
	cd aws-inventory && $(MAKE) update

clean:
	cd aws-inventory && $(MAKE) clean