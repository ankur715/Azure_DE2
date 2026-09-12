# Databricks notebook source
# Gold: fact_supply_rate — the DB-sourced and API-sourced rate feeds, conformed
# in silver_rates.py, joined to dim_customer_type and dim_date.
from pyspark.sql import functions as F

STORAGE = "<STORAGE_ACCOUNT_NAME>"
silver_path = f"abfss://silver@{STORAGE}.dfs.core.windows.net/supply_rates/"
dim_customer_type_path = f"abfss://gold@{STORAGE}.dfs.core.windows.net/dim_customer_type/"
dim_date_path = f"abfss://gold@{STORAGE}.dfs.core.windows.net/dim_date/"
gold_path = f"abfss://gold@{STORAGE}.dfs.core.windows.net/fact_supply_rate/"

# COMMAND ----------

silver = spark.read.format("delta").load(silver_path)
dim_customer_type = spark.read.format("delta").load(dim_customer_type_path)
dim_date = spark.read.format("delta").load(dim_date_path)

fact_supply_rate = (
    silver.join(dim_customer_type, on=["customer_type", "customer_segment"], how="inner")
    .withColumn("date_key", F.date_format("data_as_of", "yyyyMMdd").cast("int"))
    .join(dim_date.select("date_key"), on="date_key", how="inner")
    .select(
        "date_key",
        "customer_type_key",
        "demand_price_kw",
        "energy_price_mills_kwh",
        "source_system",
    )
)

fact_supply_rate.write.format("delta").mode("overwrite").save(gold_path)

display(fact_supply_rate)
