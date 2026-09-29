{{
  config(
    materialized='view',
    tags=['intermediate']
  )
}}

with subscriptions as (

    select * from {{ ref('stg_subscriptions') }}

),

accounts as (

    select * from {{ ref('stg_accounts') }}

),

plans as (

    select * from {{ ref('stg_plans') }}

),

joined as (

    select
        s.subscription_id,
        s.account_id,
        a.account_name,
        a.segment,
        a.region,
        a.industry,
        a.is_internal,
        a.account_created_at,
        s.plan_id,
        p.plan_name,
        p.plan_tier,
        p.billing_interval,
        s.status,
        s.mrr_cents,
        s.mrr_usd,
        s.mrr_usd * 12 as arr_usd,
        s.subscription_started_at,
        s.subscription_ended_at,
        s.churn_reason,
        s.is_currently_active,
        {{ fiscal_year('s.subscription_started_at') }} as start_fiscal_year,
        cast(date_trunc('month', s.subscription_started_at) as date) as start_month,
        cast(date_trunc('month', s.subscription_ended_at) as date) as end_month

    from subscriptions s
    inner join accounts a
        on s.account_id = a.account_id
    inner join plans p
        on s.plan_id = p.plan_id

)

select * from joined
