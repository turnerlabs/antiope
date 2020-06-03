# Battleplan-stage/qa


## Stacks wth Dependencies:


* wmcso-bcs-astra-cloud-inspect-prod
pElasticClusterName
pElasticEndpoint

* wm-scorecard-uat
pAccountTable
pAntiopeElasticSearchEndpoint
pAntiopeElasticSearchName
pBillingDataTable
pVPCTable

* wmcso-bcs-scorecards-aws-prod / -uat
pAccountTable
pBillingDataTable
pElasticClusterName
pElasticEndpoint
pVPCTable

* wm-scorecard-istreamplanet / -warnerbros / -wmto
pAccountTable
pAntiopeElasticSearchEndpoint
pAntiopeElasticSearchName
pBillingDataTable
pVPCTable

* wmcso-astra-inspection-elasticsearch-prod
pESDomainEndpoint
pESDomainName




## Prep Steps


1. Copy Lambda Layers
aws s3 cp s3://warnermedia-antiope-dev/deploy-packages/Antiope-dev-aws-lambda-layer-2020May30-1350.zip s3://warnermedia-antiope/deploy-packages/Antiope-prod-aws-lambda-layer-2020May30-1350.zip
aws s3 cp warnermedia-antiope-dev/deploy-packages/warnermedia-antiope-dev-custom-lambda-layer-2020May30-1409.zip s3://warnermedia-antiope/deploy-packages/warnermedia-antiope-prod-custom-lambda-layer-2020May30-1409.zip

1. Deploy New-Prod ; (Don't run the everything target, just the deploy.)

  1. `make promote env=prod template=https://s3.amazonaws.com/warnermedia-antiope-dev/deploy-packages/antiope-Template-Transformed-2020May30-1351.yaml`
  1. Run the cognito post-deploy
  ```bash
  cd cognito
  make post-deploy env=prod
  cd ..
  ```
  1. Disable inventory event `make disable-inventory env=prod`
  1. Deploy custom stack
```bash


  cd wmcso-antiope-customizations/

  # make layer env=qa
  # Update Manifest file
  make cft-validate-manifest env=prod
  make promote env=prod template=https://s3.amazonaws.com/warnermedia-antiope-dev/deploy-packages/custom-Template-Transformed-2020May30-1428.yaml
  aws s3 cp wm-stack-inventory-data.json s3://warnermedia-antiope/config-files/wm-stack-inventory-data.json
```
  1. Register the custom stepfunction in Antiope stack (update main manifest ; call promote)
  Edit Manifest, then:
```bash
make promote env=prod template=https://s3.amazonaws.com/warnermedia-antiope-dev/deploy-packages/antiope-Template-Transformed-2020May30-1351.yaml
```

2. Backup Old ElasticSearch
  1. Prep
    * `cd search-cluster/scripts && make deps`
  1. Register
```bash
./es_snapshot.py --domain warnermedia-antiope --bucket warnermedia-antiope --role-arn arn:aws:iam::980451846322:role/warnermedia-antiope-prod2-ElasticSe-ESSnapshotRole-YI8MOJQBBLEI --action register
```
  1. Create manual snapshot. This will be big
```bash
./es_snapshot.py --domain warnermedia-antiope  --action take --snapshot-name firstsnapshot-prod
```

3. Prep New ES
  1. Register
```bash
./es_snapshot.py --domain warnermedia-antiope-prod2 --bucket warnermedia-antiope --role-arn arn:aws:iam::980451846322:role/warnermedia-antiope-prod2-ElasticSe-ESSnapshotRole-YI8MOJQBBLEI --action register
```
  3. Purge the indices
```bash
./delete_es_index.py --domain warnermedia-antiope-prod2
```


4. Test DDB Copy
```bash
copy_ddb_table.py --source warnermedia-antiope-prod-aws-inventory-accounts --dest warnermedia-antiope-prod2-aws-inventory-accounts
copy_ddb_table.py --source warnermedia-antiope-prod-aws-inventory-vpc-inventory --dest warnermedia-antiope-prod2-aws-inventory-vpc-inventory
copy_ddb_table.py --source warnermedia-antiope-prod-wmcso-custom-wm-cft-inventory --dest warnermedia-antiope-prod-custom-wm-cft-inventory
time copy_ddb_table.py --source warnermedia-antiope-prod-aws-inventory-billing-data --dest warnermedia-antiope-prod2-aws-inventory-billing-data
```
billing data can be aborted....

## Outage Window

1. Stop Running systems
```bash
aws events disable-rule --name warnermedia-antiope-prod-aws-i-TriggerStateMachine-1A3IG5R9K5XVI
aws events disable-rule --name wm-scorecard-istreamplanet-TriggerStateMachine-1UB2LRCNMFYHK
aws events disable-rule --name wm-scorecard-mailer-warne-TriggerMailerStateMachin-ZASQDI3VM4UC
aws events disable-rule --name wm-scorecard-mailer-wmto-TriggerMailerStateMachine-5LQZYNUOHO9U
aws events disable-rule --name wm-scorecard-uat-TriggerStateMachine-18W98X485XM36
aws events disable-rule --name wm-scorecard-warnerbros-TriggerStateMachine-PE33880LZ023
aws events disable-rule --name wm-scorecard-wmto-TriggerStateMachine-V6Q2SVADJQGK
aws events disable-rule --name wmcso-bcs-astra-cloud-inspect-TriggerStateMachine-103RT71LY3HU3
aws events disable-rule --name wmcso-bcs-scorecards-aws-prod-TriggerStateMachine-QTCW6FU3JYF0
aws events disable-rule --name wmcso-bcs-scorecards-aws-uat-TriggerStateMachine-1GAKHJIY5YH70
```

2. Trigger final snapshot of old ES Cluster
```bash
./es_snapshot.py --domain warnermedia-antiope  --action take --snapshot-name finalsnapshot-prod
```
2. Copy DDB tables using my script. (billing data make take time) - See commands below
3. Trigger Final ES Restore on chosen indices
```bash
./es_snapshot.py --domain warnermedia-antiope-prod2 --action restore --snapshot-name finalsnapshot-prod
```
4. Run the Searchcluster post-deploy to enable the S3 event and any non-copied indexes
```bash
cd search-cluster
make post-deploy env=prod
cd ..
```

5. Subscribe to the new NewAccount topic (prod only)
6. manual trigger
  * make trigger-inventory env=prod
  * Validate no failures

7. Update external Templates
(see above)


8. Re-Enable systems
```bash
aws events enable-rule --name wm-scorecard-mailer-wmto-TriggerMailerStateMachine-5LQZYNUOHO9U
aws events enable-rule --name wm-scorecard-warnerbros-TriggerStateMachine-PE33880LZ023
aws events enable-rule --name wm-scorecard-wmto-TriggerStateMachine-V6Q2SVADJQGK
aws events enable-rule --name wmcso-bcs-astra-cloud-inspect-TriggerStateMachine-103RT71LY3HU3
aws events enable-rule --name wmcso-bcs-scorecards-aws-prod-TriggerStateMachine-QTCW6FU3JYF0
aws events enable-rule --name wmcso-bcs-scorecards-aws-uat-TriggerStateMachine-1GAKHJIY5YH70
make enable-inventory env=prod
```



