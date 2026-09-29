{{
  config(
    materialized='table',
    tags=['marts', 'core']
  )
}}

with accounts as (

    select * from {{ ref('stg_accounts') }}

),

activation as (

    select
        account_id,
        is_activated,
        qualifying_event_count,
        first_product_event_at
    from {{ ref('int_account_activation') }}

),

current_sub as (

    select
        account_id,
        max(case when is_currently_active then mrr_usd end) as current_mrr_usd,
        max(case when is_currently_active then arr_usd end) as current_arr_usd,
        max(case when is_currently_active then plan_tier end) as current_plan_tier,
        count(*) as lifetime_subscription_count
    from {{ ref('int_subscription_spine') }}
    group by 1

),

final as (

    select
        {{ dbt_utils.generate_surrogate_key(['a.account_id']) }} as account_sk,
        a.account_id,
        a.account_name,
        a.industry,
        a.segment,
        a.region,
        a.account_created_at,
        a.is_internal,
        {{ fiscal_year('a.account_created_at') }} as account_created_fiscal_year,
        coalesce(act.is_activated, false) as is_activated,
        act.qualifying_event_count,
        act.first_product_event_at,
        cs.current_mrr_usd,
        cs.current_arr_usd,
        cs.current_plan_tier,
        coalesce(cs.lifetime_subscription_count, 0) as lifetime_subscription_count,
        {{ dbt.current_timestamp() }} as dbt_updated_at

    from accounts a
    left join activation act
        on a.account_id = act.account_id
    left join current_sub cs
        on a.account_id = cs.account_id

)

select * from final
