{{
  config(
    materialized='table',
    tags=['marts', 'fact', 'orders']
  )
}}

with order_lines as (
    select * from {{ ref('int_order_lines_enriched') }}
),

customers as (
    select customer_sk, customer_nk from {{ ref('dim_customer') }}
),

products as (
    select product_sk, product_nk from {{ ref('dim_product') }}
),

dates as (
    select date_sk, date_day from {{ ref('dim_date') }}
),

ship_from as (
    select location_sk, location_nk from {{ ref('dim_location') }}
),

ship_to as (
    select location_sk, location_nk from {{ ref('dim_location') }}
)

select
    {{ generate_surrogate_key(['ol.order_line_id']) }} as order_line_sk,
    ol.order_line_id as order_line_nk,
    ol.order_id,
    ol.order_number,
    c.customer_sk,
    p.product_sk,
    d.date_sk as order_date_sk,
    ol.order_date,
    sf.location_sk as ship_from_location_sk,
    st.location_sk as ship_to_location_sk,
    ol.requested_ship_date,
    ol.order_status,
    ol.order_channel,
    ol.quantity,
    ol.unit_price,
    ol.discount_pct,
    ol.tax_amount,
    ol.line_net_amount,
    ol.line_gross_amount,
    ol.unit_cost,
    ol.line_cogs,
    ol.line_gross_margin,
    ol.line_margin_pct,
    ol.currency_code,
    ol.sales_rep,
    ol.created_at,
    ol.updated_at,
    current_timestamp as dbt_updated_at
from order_lines ol
left join customers c on ol.customer_id = c.customer_nk
left join products p on ol.product_id = p.product_nk
left join dates d on ol.order_date = d.date_day
left join ship_from sf on ol.ship_from_location_id = sf.location_nk
left join ship_to st on ol.ship_to_location_id = st.location_nk
