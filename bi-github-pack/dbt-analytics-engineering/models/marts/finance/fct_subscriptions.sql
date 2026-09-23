{{
  config(
    materialized='table',
    tags=['marts', 'finance']
  )
}}

with spine as (

    select * from {{ ref('int_subscription_spine') }}

),

final as (

    select
        {{ dbt_utils.generate_surrogate_key(['subscription_id']) }} as subscription_sk,
        subscription_id,
        account_id,
        account_name,
        segment,
        region,
        industry,
        is_internal,
        plan_id,
        plan_name,
        plan_tier,
        billing_interval,
        status,
        mrr_cents,
        mrr_usd,
        arr_usd,
        subscription_started_at,
        subscription_ended_at,
        churn_reason,
        is_currently_active,
        start_fiscal_year,
        start_month,
        end_month,
        case
            when subscription_ended_at is null
                then {{ dbt.datediff('subscription_started_at', dbt.current_timestamp(), 'day') }}
            else {{ dbt.datediff('subscription_started_at', 'subscription_ended_at', 'day') }}
        end as tenure_days,
        case
            when status = 'churned' then true
            else false
        end as is_churned,
        case
            when status = 'upgraded' then true
            else false
        end as is_upgrade,
        {{ dbt.current_timestamp() }} as dbt_updated_at

    from spine

)

select * from final
