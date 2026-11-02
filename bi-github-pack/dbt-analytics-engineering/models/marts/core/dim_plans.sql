{{
  config(
    materialized='table',
    tags=['marts', 'core']
  )
}}

with plans as (

    select * from {{ ref('stg_plans') }}

),

final as (

    select
        {{ dbt_utils.generate_surrogate_key(['plan_id']) }} as plan_sk,
        plan_id,
        plan_name,
        plan_tier,
        billing_interval,
        price_cents,
        list_price_usd,
        seat_limit,
        is_active,
        case
            when billing_interval = 'annual' then list_price_usd
            else list_price_usd * 12
        end as list_arr_usd,
        {{ dbt.current_timestamp() }} as dbt_updated_at

    from plans

)

select * from final
