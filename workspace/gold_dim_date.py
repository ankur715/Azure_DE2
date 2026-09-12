# Databricks notebook source
# Gold: dim_date — spans the years seen in generation data and the calendar
# dates seen in supply_rates, so both facts can join to it.
from pyspark.sql import functions as F

STORAGE = "nypade2dls32tf2h3w4elwi"
gold_path = f"abfss://gold@{STORAGE}.dfs.core.windows.net/dim_date/"

# COMMAND ----------

date_range = spark.sql(
    "SELECT explode(sequence(to_date('2012-01-01'), current_date(), interval 1 day)) AS full_date"
)

dim_date = date_range.select(
    F.date_format("full_date", "yyyyMMdd").cast("int").alias("date_key"),
    "full_date",
    F.year("full_date").alias("year"),
    F.month("full_date").alias("month"),
    F.dayofmonth("full_date").alias("day"),
    F.date_format("full_date", "EEEE").alias("day_name"),
    F.quarter("full_date").alias("quarter"),
)

dim_date.write.format("delta").mode("overwrite").save(gold_path)

display(dim_date)
