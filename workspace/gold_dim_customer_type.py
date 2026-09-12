# Databricks notebook source
# Gold: dim_customer_type — unifies the DB-sourced (governmental) and
# API-sourced (business) rate customer segments behind one dimension.
from pyspark.sql import functions as F
from pyspark.sql.window import Window

STORAGE = "<STORAGE_ACCOUNT_NAME>"
silver_path = f"abfss://silver@{STORAGE}.dfs.core.windows.net/supply_rates/"
gold_path = f"abfss://gold@{STORAGE}.dfs.core.windows.net/dim_customer_type/"

# COMMAND ----------

customer_types = (
    spark.read.format("delta")
    .load(silver_path)
    .select("customer_type", "customer_segment")
    .distinct()
    .withColumn(
        "customer_type_key",
        F.row_number().over(Window.orderBy("customer_type", "customer_segment")),
    )
    .select("customer_type_key", "customer_type", "customer_segment")
)

customer_types.write.format("delta").mode("overwrite").save(gold_path)

display(customer_types)
