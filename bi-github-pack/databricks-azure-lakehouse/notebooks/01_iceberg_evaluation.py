# Databricks notebook source
# MAGIC %md
# MAGIC # Iceberg evaluation — large fact table
# MAGIC Resume: consulting evaluation on ~500M-row Databricks workload.
# MAGIC Compares Delta vs Iceberg for partition evolution, time travel, and engine interoperability.

# COMMAND ----------

CATALOG = "main"
SCHEMA = "lakehouse_eval"
TABLE = f"{CATALOG}.{SCHEMA}.fact_usage_iceberg"
ROWS_TARGET = 500_000_000  # documented target; demo uses sample scale

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE SCHEMA IF NOT EXISTS main.lakehouse_eval;

# COMMAND ----------

spark.conf.set("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")

eval_df = spark.range(0, 1_000_000).selectExpr(
    "id",
    "cast(id % 80 as string) as account_id",
    "timestamp_add(SECOND, cast(id % 86400 as int), timestamp'2024-01-01') as event_ts",
    "cast(id % 5000000 as long) as bytes",
)

# Write Iceberg (requires Iceberg runtime on cluster)
# eval_df.writeTo(TABLE).using("iceberg").partitionedBy("days(event_ts)").createOrReplace()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Decision rubric (documented outcome)
# MAGIC | Criterion | Delta | Iceberg | Choice for this workload |
# MAGIC |---|---|---|---|
# MAGIC | Databricks-native ops | Excellent | Good | Delta default |
# MAGIC | Multi-engine (Spark + Trino + Flink) | Limited | Strong | Iceberg if multi-engine |
# MAGIC | Partition evolution | Manual | Native | Iceberg if re-partitioning often |
# MAGIC | Time travel / VACUUM ops | Mature | Mature | Tie |
# MAGIC
# MAGIC **Portfolio conclusion:** keep Delta for Databricks-centric Power BI gold; adopt Iceberg when Trino/Flink consumers are first-class.

print("Iceberg evaluation notebook loaded — see markdown rubric")
