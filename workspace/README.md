Databricks notebooks (source format): silver cleansing per source and gold
dimensional-model builds (dim_facility, dim_date, dim_customer_type,
fact_generation, fact_supply_rate).

Each notebook reads `STORAGE = "<STORAGE_ACCOUNT_NAME>"` — replace with your own
ADLS Gen2 storage account name before importing/running these in a workspace.
