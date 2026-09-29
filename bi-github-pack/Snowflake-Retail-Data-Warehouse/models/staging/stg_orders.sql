{{
  config(
    materialized='view',
    tags=['staging', 'erp']
  )
}}

with source as (
    select * from {{ source('raw_erp', 'raw_orders') }}
),

renamed as (
    select
        cast(order_id as varchar) as order_id,
        cast(order_line_id as varchar) as order_line_id,
        cast(order_number as varchar) as order_number,
        cast(customer_id as varchar) as customer_id,
        cast(product_id as varchar) as product_id,
        cast(order_date as date) as order_date,
        cast(requested_ship_date as date) as requested_ship_date,
        upper(trim(order_status)) as order_status,
        upper(trim(order_channel)) as order_channel,
        cast(quantity as integer) as quantity,
        cast(unit_price as decimal(18, 4)) as unit_price,
        cast(discount_pct as decimal(7, 4)) as discount_pct,
        cast(tax_amount as decimal(18, 4)) as tax_amount,
        cast(ship_from_location_id as varchar) as ship_from_location_id,
        cast(ship_to_location_id as varchar) as ship_to_location_id,
        trim(currency_code) as currency_code,
        cast(sales_rep as varchar) as sales_rep,
        cast(created_at as timestamp) as created_at,
        cast(updated_at as timestamp) as updated_at,
        cast(_loaded_at as timestamp) as _loaded_at,
        cast(_source_system as varchar) as _source_system
    from source
),

enriched as (
    select
        *,
        round(quantity * unit_price * (1 - coalesce(discount_pct, 0)), 2) as line_net_amount,
        round(quantity * unit_price * (1 - coalesce(discount_pct, 0)) + coalesce(tax_amount, 0), 2) as line_gross_amount,
        row_number() over (
            partition by order_line_id
            order by updated_at desc, _loaded_at desc
        ) as _row_num
    from renamed
)

select
    order_id,
    order_line_id,
    order_number,
    customer_id,
    product_id,
    order_date,
    requested_ship_date,
    order_status,
    order_channel,
    quantity,
    unit_price,
    discount_pct,
    tax_amount,
    line_net_amount,
    line_gross_amount,
    ship_from_location_id,
    ship_to_location_id,
    currency_code,
    sales_rep,
    created_at,
    updated_at,
    _loaded_at,
    _source_system
from enriched
where _row_num = 1
