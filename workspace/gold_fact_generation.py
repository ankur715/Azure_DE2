# Databricks notebook source
# Gold: fact_generation — net generation by facility/year, joined to dim_facility.
from pyspark.sql import functions as F

STORAGE = "<STORAGE_ACCOUNT_NAME>"
silver_path = f"abfss://silver@{STORAGE}.dfs.core.windows.net/generation/"
dim_facility_path = f"abfss://gold@{STORAGE}.dfs.core.windows.net/dim_facility/"
gold_path = f"abfss://gold@{STORAGE}.dfs.core.windows.net/fact_generation/"

# COMMAND ----------

silver = spark.read.format("delta").load(silver_path)
dim_facility = spark.read.format("delta").load(dim_facility_path)

fact_generation = (
    silver.join(dim_facility, on="facility_name", how="inner")
    .select("facility_key", "year", "net_generation_mwh")
)

fact_generation.write.format("delta").mode("overwrite").save(gold_path)

display(fact_generation)
