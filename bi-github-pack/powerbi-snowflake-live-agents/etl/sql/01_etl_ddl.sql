CREATE DATABASE IF NOT EXISTS ANALYTICS;
CREATE SCHEMA IF NOT EXISTS ANALYTICS.RAW;
CREATE SCHEMA IF NOT EXISTS ANALYTICS.MARTS;

CREATE OR REPLACE TABLE ANALYTICS.RAW.CUSTOMERS (
  customer_id STRING, customer_name STRING, region_name STRING,
  country_code STRING, segment STRING, is_active STRING
);
CREATE OR REPLACE TABLE ANALYTICS.RAW.PRODUCTS (
  product_id STRING, product_name STRING, product_category STRING,
  brand STRING, unit_cost FLOAT
);
CREATE OR REPLACE TABLE ANALYTICS.RAW.ORDERS (
  order_id STRING, customer_id STRING, order_date STRING,
  order_status STRING, order_channel STRING, currency_code STRING
);
CREATE OR REPLACE TABLE ANALYTICS.RAW.ORDER_LINES (
  order_line_id STRING, order_id STRING, product_id STRING,
  quantity NUMBER, unit_price FLOAT, discount_pct FLOAT, tax_amount FLOAT
);

CREATE OR REPLACE TABLE ANALYTICS.MARTS.DIM_CUSTOMER (
  customer_sk STRING, customer_id STRING, customer_name STRING,
  region_name STRING, country_code STRING, segment STRING, is_active BOOLEAN
);
CREATE OR REPLACE TABLE ANALYTICS.MARTS.DIM_PRODUCT (
  product_sk STRING, product_id STRING, product_name STRING,
  product_category STRING, brand STRING, unit_cost FLOAT
);
CREATE OR REPLACE TABLE ANALYTICS.MARTS.DIM_DATE (
  date_sk STRING, date_day DATE, year NUMBER, month NUMBER, quarter NUMBER
);
CREATE OR REPLACE TABLE ANALYTICS.MARTS.FCT_ORDERS (
  order_line_sk STRING, order_line_id STRING, order_id STRING,
  customer_sk STRING, customer_id STRING, product_sk STRING, product_id STRING,
  order_date DATE, order_status STRING, order_channel STRING, currency_code STRING,
  region_name STRING, country_code STRING, product_category STRING, product_name STRING,
  quantity NUMBER, unit_price FLOAT, discount_pct FLOAT, tax_amount FLOAT,
  line_net_amount FLOAT, line_cogs FLOAT, line_gross_margin FLOAT
);
