{{
  config(
    materialized='table',
    tags=['marts', 'dimension']
  )
}}

with products as (
    select * from {{ ref('stg_products') }}
)

select
    {{ generate_surrogate_key(['product_id']) }} as product_sk,
    product_id as product_nk,
    sku,
    product_name,
    product_category,
    product_subcategory,
    brand,
    unit_cost,
    list_price,
    unit_of_measure,
    weight_lbs,
    status,
    supplier_id,
    supplier_name,
    case
        when list_price > 0 then round((list_price - unit_cost) / list_price, 4)
        else null
    end as list_margin_pct,
    created_at as product_created_at,
    updated_at as product_updated_at,
    current_timestamp as dbt_updated_at
from products
