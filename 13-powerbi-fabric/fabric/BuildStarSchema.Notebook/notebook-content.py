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
# Copy these files into the lakehouse before running:
# 
# - `data/bronze/sales_export.csv` to `Files/bronze/`
# - `data/reference/` to `Files/reference/`
# - `data/gold/fact_budget.csv` to `Files/gold/`
# - `data/source/product_price_history.csv` and `data/source/inventory_count.csv` to `Files/source/`
# 
# Bronze is the export as it landed. Silver drops blank, non-positive, and duplicate lines. Gold is the star schema. The tested numbers come from `harbor/model.py`. This notebook is the same shape in Spark. The semantic model does not compute amounts again. It sums them.

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
# It already uses the launch price, so a later price change does not rewrite the plan.
budget = spark.read.option("header", True).csv("Files/gold/fact_budget.csv")
budget.write.mode("overwrite").format("delta").saveAsTable("fact_budget")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# # Price history and the month-end count
# 
# A price change closes yesterday's row and opens a new one. The sale keeps the version that covered the order date. `DimProduct[List Price]` stays the price a customer would pay today.
# 
# Inventory is a clipboard count on the last day of each month. The notebook stores every snapshot. The measure `Inventory units` keeps only the last snapshot in the filter.

# CELL ********************

from pyspark.sql.window import Window

BATCH_ID = "2026-01-06"
events = (
    spark.read.option("header", True)
    .csv("Files/source/product_price_history.csv")
    .withColumn("valid_from", F.to_date("effective_date"))
    .withColumn("list_price", F.col("list_price").cast("decimal(18,2)"))
)
product_key = products.select(F.col("Product").alias("product"), F.col("ProductKey").cast("int").alias("ProductKey"))
by_product = Window.partitionBy("product").orderBy("valid_from")
by_catalog = Window.orderBy("ProductKey", "valid_from")
versions = (
    events.join(product_key, "product")
    .withColumn("next_from", F.lead("valid_from").over(by_product))
    .withColumn(
        "Valid To",
        F.when(F.col("next_from").isNull(), F.to_date(F.lit("9999-12-31"))).otherwise(F.date_sub(F.col("next_from"), 1)),
    )
    .withColumn("Is Current", F.when(F.col("next_from").isNull(), F.lit("true")).otherwise(F.lit("false")))
    .withColumn("ProductPriceKey", F.row_number().over(by_catalog))
    .select(
        "ProductPriceKey",
        "ProductKey",
        F.col("product").alias("Product"),
        F.col("list_price").alias("List Price"),
        F.col("valid_from").alias("Valid From"),
        "Valid To",
        "Is Current",
    )
)
versions.write.mode("overwrite").format("delta").saveAsTable("dim_product_price")

priced = (
    fact.join(
        versions.select("ProductKey", "ProductPriceKey", "Valid From", "Valid To"),
        "ProductKey",
    )
    .where((F.col("OrderDate") >= F.col("Valid From")) & (F.col("OrderDate") <= F.col("Valid To")))
    .withColumn("Batch Id", F.lit(BATCH_ID))
    .drop("Valid From", "Valid To")
)
priced.write.mode("overwrite").format("delta").saveAsTable("fact_sales")

counts = spark.read.option("header", True).csv("Files/source/inventory_count.csv")
inventory = (
    counts
    .join(stores.select(F.col("StoreKey").cast("int"), F.col("Store").alias("store")), "store")
    .join(products.select(F.col("ProductKey").cast("int"), F.col("Product").alias("product")), "product")
    .withColumn("DateKey", F.date_format(F.to_date("count_date"), "yyyyMMdd").cast("int"))
    .withColumn("Units On Hand", F.col("units_on_hand").cast("int"))
    .withColumn("Batch Id", F.lit(BATCH_ID))
    .select("DateKey", "StoreKey", "ProductKey", "Units On Hand", "Batch Id")
)
inventory.write.mode("overwrite").format("delta").saveAsTable("fact_inventory")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# # What this notebook does not do
# 
# It does not define revenue, margin, year to date, or weeks of supply. Those names belong to the semantic model. After this notebook finishes, refresh the Harbor semantic model, or point its partitions at these Delta tables and switch them to Direct Lake. The Python tests certify the numbers. This notebook was not executed in Spark.
