
ifndef env
# $(error env is not set)
	env ?= dev
endif

ifdef CONFIG
	include $(CONFIG)
	export
else
	include config.$(env)
	export
endif

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

search-deploy:
	cd search-cluster && $(MAKE) deploy

search-update:
	cd search-clustery && $(MAKE) update

clean:
	cd aws-inventory && $(MAKE) clean
	cd search-cluster && $(MAKE) clean

trigger-inventory:
	./bin/trigger_inventory.sh $(STACK_PREFIX)-$(env)-aws-inventory

sync-resources:
	aws s3 sync s3://$(BUCKET)/Resources/$(type) Scratch/Resources/$(env)/$(type)
	open Scratch/Resources/$(env)/$(type)