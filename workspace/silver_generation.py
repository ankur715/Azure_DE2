# Databricks notebook source
# Silver: cleanse NYPA net generation (CSV-sourced) bronze parquet.

# COMMAND ----------

from pyspark.sql import functions as F

bronze_path = "abfss://bronze@nypade2dls32tf2h3w4elwi.dfs.core.windows.net/generation/"

df = spark.read.parquet(bronze_path)

silver_df = (
    df.select(
        F.col("year").cast("int").alias("year"),
        F.trim(F.col("nypa_facility_name")).alias("facility_name"),
        F.col("net_generation_mwh").cast("double").alias("net_generation_mwh"),
    )
    .filter(F.col("year").isNotNull() & F.col("facility_name").isNotNull())
    .dropDuplicates(["year", "facility_name"])
)

# COMMAND ----------

silver_path = "abfss://silver@nypade2dls32tf2h3w4elwi.dfs.core.windows.net/generation/"
silver_df.write.format("delta").mode("overwrite").save(silver_path)

display(silver_df)
