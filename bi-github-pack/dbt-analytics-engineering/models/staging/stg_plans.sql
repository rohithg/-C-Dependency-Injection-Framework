{{
  config(
    materialized='view',
    tags=['staging']
  )
}}

with source as (

    select * from {{ ref('seed_plans') }}

),

renamed as (

    select
        plan_id,
        trim(plan_name) as plan_name,
        lower(trim(plan_tier)) as plan_tier,
        lower(trim(billing_interval)) as billing_interval,
        cast(price_cents as {{ dbt.type_int() }}) as price_cents,
        {{ cents_to_dollars('price_cents') }} as list_price_usd,
        cast(seat_limit as {{ dbt.type_int() }}) as seat_limit,
        cast(is_active as boolean) as is_active,
        {{ dbt.current_timestamp() }} as _loaded_at

    from source

)

select * from renamed
