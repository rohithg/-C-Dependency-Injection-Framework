{{
  config(
    materialized='view',
    tags=['intermediate', 'finance']
  )
}}

/*
  Month-end MRR spine per account.
  A subscription contributes to a month if it was still active at month end:
    started_at < next_month_start
    and (ended_at is null or ended_at >= next_month_start)
*/

with recursive subscriptions as (

    select
        subscription_id,
        account_id,
        status,
        mrr_usd,
        subscription_started_at,
        subscription_ended_at,
        is_internal
    from {{ ref('int_subscription_spine') }}
    where not is_internal
      and status in ('active', 'churned', 'upgraded')
      and mrr_usd > 0

),

date_bounds as (

    select
        cast(date_trunc('month', min(subscription_started_at)) as date) as min_month,
        cast(date_trunc('month', {{ dbt.current_timestamp() }}) as date) as max_month
    from subscriptions

),

month_spine as (

    select min_month as month_start, max_month
    from date_bounds

    union all

    select
        cast({{ dbt.dateadd('month', 1, 'month_start') }} as date) as month_start,
        max_month
    from month_spine
    where cast({{ dbt.dateadd('month', 1, 'month_start') }} as date) <= max_month

),

monthly_mrr as (

    select
        m.month_start,
        s.account_id,
        s.subscription_id,
        s.mrr_usd,
        s.status,
        case
            when s.subscription_ended_at is not null
             and cast(date_trunc('month', s.subscription_ended_at) as date) = m.month_start
             and s.status in ('churned', 'upgraded')
            then true
            else false
        end as ended_this_month

    from month_spine m
    inner join subscriptions s
        on s.subscription_started_at < {{ dbt.dateadd('month', 1, 'm.month_start') }}
        and (
            s.subscription_ended_at is null
            or s.subscription_ended_at >= {{ dbt.dateadd('month', 1, 'm.month_start') }}
        )

),

account_month as (

    select
        month_start,
        account_id,
        sum(mrr_usd) as mrr_usd,
        max(ended_this_month) as had_ending_subscription,
        count(distinct subscription_id) as active_subscription_count

    from monthly_mrr
    group by 1, 2

)

select * from account_month
