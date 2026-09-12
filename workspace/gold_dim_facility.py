# Databricks notebook source
# Gold: dim_facility — SCD type 1, surrogate key per NYPA facility.
from pyspark.sql import functions as F
from pyspark.sql.window import Window

STORAGE = "<STORAGE_ACCOUNT_NAME>"
silver_path = f"abfss://silver@{STORAGE}.dfs.core.windows.net/generation/"
gold_path = f"abfss://gold@{STORAGE}.dfs.core.windows.net/dim_facility/"

# COMMAND ----------

facilities = (
    spark.read.parquet(silver_path)
    .select("facility_name")
    .distinct()
    .withColumn("facility_key", F.row_number().over(Window.orderBy("facility_name")))
    .select("facility_key", "facility_name")
)

facilities.write.format("delta").mode("overwrite").save(gold_path)

display(facilities)
