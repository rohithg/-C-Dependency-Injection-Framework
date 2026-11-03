# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse_name": "HarborLakehouse",
# META       "default_lakehouse_workspace_id": ""
# META     }
# META   }
# META }

# MARKDOWN ********************

# # Build the Harbor star schema
# 
# Copy `data/bronze/sales_export.csv` to `Files/bronze/` and the three files in `data/reference/` to `Files/reference/` before running.
# 
# Bronze is the export as it landed. Silver drops blank, non-positive, and duplicate lines. Gold is the star schema: one date row per day, and facts that hold keys plus additive amounts. The semantic model does not compute those amounts again. It sums them.

# CELL ********************

from pyspark.sql import functions as F

bronze = (
    spark.read
    .option("header", True)
    .csv("Files/bronze/sales_export.csv")
    .withColumn("qty_number", F.col("qty").cast("int"))
)

bad_qty = bronze.where(F.col("qty_number").isNull() | (F.col("qty_number") <= 0))
candidates = bronze.where(F.col("qty_number") > 0)

identity = ["order_id", "order_date", "store", "product", "customer", "qty", "unit_price", "discount"]
duplicates = candidates.groupBy(*identity).count().where(F.col("count") > 1)
quarantine = bad_qty.withColumn("reason", F.lit("quantity is blank or not positive"))
silver = candidates.dropDuplicates(identity)

(
    quarantine.write.mode("overwrite").format("delta").saveAsTable("quarantine_sales")
)
print("quarantined", quarantine.count(), "duplicate groups", duplicates.count())

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

stores = spark.read.option("header", True).csv("Files/reference/stores.csv")
products = spark.read.option("header", True).csv("Files/reference/products.csv")
customers = spark.read.option("header", True).csv("Files/reference/customers.csv")

fact = (
    silver
    .join(stores.select("StoreKey", F.col("Store").alias("store")), "store")
    .join(products.select("ProductKey", "Unit Cost", F.col("Product").alias("product")), "product")
    .join(customers.select("CustomerKey", F.col("Customer").alias("customer")), "customer")
    .withColumn("OrderDate", F.to_date("order_date"))
    .withColumn("ShipDate", F.to_date("ship_date"))
    .withColumn("DateKey", F.date_format("OrderDate", "yyyyMMdd").cast("int"))
    .withColumn("Quantity", F.col("qty_number"))
    .withColumn("Net Amount", F.round(F.col("unit_price").cast("decimal(18,2)") * F.col("Quantity") - F.col("discount").cast("decimal(18,2)"), 2))
    .withColumn("Cost Amount", F.round(F.col("Unit Cost").cast("decimal(18,2)") * F.col("Quantity"), 2))
    .withColumn("Discount Amount", F.col("discount").cast("decimal(18,2)"))
    .select(
        F.col("order_id").cast("int").alias("OrderId"),
        "OrderDate", "ShipDate", "DateKey",
        F.col("ProductKey").cast("int"),
        F.col("StoreKey").cast("int"),
        F.col("CustomerKey").cast("int"),
        "Quantity", "Net Amount", "Cost Amount", "Discount Amount",
    )
)

(
    fact.write.mode("overwrite").format("delta").saveAsTable("fact_sales")
)
stores.write.mode("overwrite").format("delta").saveAsTable("dim_store")
products.write.mode("overwrite").format("delta").saveAsTable("dim_product")
customers.write.mode("overwrite").format("delta").saveAsTable("dim_customer")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# A date table with no gaps. Days that had no orders still get a row.
start = "2024-01-01"
end = "2026-01-05"
dates = (
    spark.sql(f"SELECT explode(sequence(to_date('{start}'), to_date('{end}'), interval 1 day)) AS Date")
    .withColumn("DateKey", F.date_format("Date", "yyyyMMdd").cast("int"))
    .withColumn("Year", F.year("Date"))
    .withColumn("Quarter", F.concat(F.lit("Q"), F.quarter("Date").cast("string")))
    .withColumn("Month Number", F.month("Date"))
    .withColumn("Month Name", F.date_format("Date", "MMMM"))
    .withColumn("Year Month", F.date_format("Date", "yyyy-MM"))
    .withColumn("Year Month Number", (F.year("Date") * 100 + F.month("Date")))
    .withColumn("Day of Week", F.date_format("Date", "EEEE"))
    # Spark numbers Sunday as 1. The semantic model numbers Monday as 1.
    .withColumn("Weekday Number", F.when(F.dayofweek("Date") == 1, F.lit(7)).otherwise(F.dayofweek("Date") - 1))
    .withColumn("Day Type", F.when(F.dayofweek("Date").isin(1, 7), F.lit("Weekend")).otherwise(F.lit("Weekday")))
)
dates.write.mode("overwrite").format("delta").saveAsTable("dim_date")

# The monthly plan is produced by harbor/model.py, not from the orders.
# Upload data/gold/fact_budget.csv to Files/gold/ before this cell.
budget = spark.read.option("header", True).csv("Files/gold/fact_budget.csv")
budget.write.mode("overwrite").format("delta").saveAsTable("fact_budget")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# # What this notebook does not do
# 
# It does not define revenue, margin, or year to date. Those names belong to the semantic model. After this notebook finishes, refresh the Harbor semantic model, or point its partitions at these Delta tables and switch them to Direct Lake.
