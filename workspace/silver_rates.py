# Databricks notebook source
# Silver: conform the two rate sources (DB-sourced governmental rates, API-sourced
# business rates) into one shape so gold can treat them as a single fact.
from pyspark.sql import functions as F

STORAGE = "<STORAGE_ACCOUNT_NAME>"
bronze_gov_path = f"abfss://bronze@{STORAGE}.dfs.core.windows.net/governmental_rates/"
bronze_biz_path = f"abfss://bronze@{STORAGE}.dfs.core.windows.net/business_rates/"

# COMMAND ----------

gov_df = spark.read.parquet(bronze_gov_path)

gov_silver = gov_df.select(
    F.lit("governmental").alias("customer_type"),
    F.trim(F.col("governmental_entity")).alias("customer_segment"),
    F.col("period").alias("nyiso_zone_or_period"),
    F.col("production_demand_price_kw").cast("double").alias("demand_price_kw"),
    F.col("production_energy_price_mills_kwh").cast("double").alias("energy_price_mills_kwh"),
    F.to_date("data_as_of").alias("data_as_of"),
    F.lit("azure_sql").alias("source_system"),
)

# COMMAND ----------

biz_df = spark.read.json(bronze_biz_path)

biz_silver = biz_df.select(
    F.trim(F.col("customer_type")).alias("customer_type"),
    F.trim(F.col("customer_type")).alias("customer_segment"),
    F.col("nyiso_zone").alias("nyiso_zone_or_period"),
    F.col("demand_price_kw").cast("double").alias("demand_price_kw"),
    F.col("energy_price_mills_kwh").cast("double").alias("energy_price_mills_kwh"),
    F.to_date("data_as_of").alias("data_as_of"),
    F.lit("socrata_rest_api").alias("source_system"),
)

# COMMAND ----------

silver_rates = gov_silver.unionByName(biz_silver).dropna(subset=["data_as_of"])

silver_path = f"abfss://silver@{STORAGE}.dfs.core.windows.net/supply_rates/"
silver_rates.write.format("delta").mode("overwrite").save(silver_path)

display(silver_rates)
