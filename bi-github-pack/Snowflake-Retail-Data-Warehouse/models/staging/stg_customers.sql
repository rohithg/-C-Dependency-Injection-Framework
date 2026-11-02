{{
  config(
    materialized='view',
    tags=['staging', 'erp', 'crm']
  )
}}

with source as (
    select * from {{ source('raw_erp', 'raw_customers') }}
),

renamed as (
    select
        cast(customer_id as varchar) as customer_id,
        cast(customer_code as varchar) as customer_code,
        trim(customer_name) as customer_name,
        trim(customer_type) as customer_type,
        trim(industry) as industry,
        trim(email) as email,
        trim(phone) as phone,
        trim(billing_city) as billing_city,
        trim(billing_state) as billing_state,
        trim(billing_country) as billing_country,
        trim(shipping_city) as shipping_city,
        trim(shipping_state) as shipping_state,
        trim(shipping_country) as shipping_country,
        cast(credit_limit as decimal(18, 2)) as credit_limit,
        upper(trim(status)) as status,
        cast(account_manager as varchar) as account_manager,
        cast(created_at as timestamp) as created_at,
        cast(updated_at as timestamp) as updated_at,
        cast(_loaded_at as timestamp) as _loaded_at,
        cast(_source_system as varchar) as _source_system
    from source
),

deduped as (
    select
        *,
        row_number() over (
            partition by customer_id
            order by updated_at desc, _loaded_at desc
        ) as _row_num
    from renamed
)

select
    customer_id,
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
    created_at,
    updated_at,
    _loaded_at,
    _source_system
from deduped
where _row_num = 1
