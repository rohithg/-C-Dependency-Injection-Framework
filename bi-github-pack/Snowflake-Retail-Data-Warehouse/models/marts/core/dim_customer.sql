{{
  config(
    materialized='table',
    tags=['marts', 'dimension']
  )
}}

with customers as (
    select * from {{ ref('stg_customers') }}
)

select
    {{ generate_surrogate_key(['customer_id']) }} as customer_sk,
    customer_id as customer_nk,
    customer_code,
    customer_name,
    customer_type,
    industry,
    email,
    phone,
    billing_city,
    billing_state,
    billing_country,
    shipping_city,
    shipping_state,
    shipping_country,
    credit_limit,
    status,
    account_manager,
    created_at as customer_created_at,
    updated_at as customer_updated_at,
    current_timestamp as dbt_updated_at
from customers
