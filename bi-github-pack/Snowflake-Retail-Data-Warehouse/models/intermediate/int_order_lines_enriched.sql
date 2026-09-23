{{
  config(
    materialized='view',
    tags=['intermediate', 'orders']
  )
}}

with orders as (
    select * from {{ ref('stg_orders') }}
),

customers as (
    select
        customer_id,
        customer_name,
        customer_type,
        status as customer_status
    from {{ ref('stg_customers') }}
),

products as (
    select
        product_id,
        sku,
        product_name,
        product_category,
        unit_cost,
        list_price
    from {{ ref('stg_products') }}
),

joined as (
    select
        o.order_id,
        o.order_line_id,
        o.order_number,
        o.customer_id,
        c.customer_name,
        c.customer_type,
        c.customer_status,
        o.product_id,
        p.sku,
        p.product_name,
        p.product_category,
        o.order_date,
        o.requested_ship_date,
        o.order_status,
        o.order_channel,
        o.quantity,
        o.unit_price,
        o.discount_pct,
        o.tax_amount,
        o.line_net_amount,
        o.line_gross_amount,
        p.unit_cost,
        round(o.quantity * coalesce(p.unit_cost, 0), 2) as line_cogs,
        round(o.line_net_amount - (o.quantity * coalesce(p.unit_cost, 0)), 2) as line_gross_margin,
        {{ safe_divide('o.line_net_amount - (o.quantity * coalesce(p.unit_cost, 0))', 'nullif(o.line_net_amount, 0)') }} as line_margin_pct,
        o.ship_from_location_id,
        o.ship_to_location_id,
        o.currency_code,
        o.sales_rep,
        o.created_at,
        o.updated_at
    from orders o
    left join customers c on o.customer_id = c.customer_id
    left join products p on o.product_id = p.product_id
)

select * from joined
