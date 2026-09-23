{{
  config(
    materialized='table',
    tags=['metrics', 'finance']
  )
}}

/*
  ARR (Annual Recurring Revenue) — metrics-as-code definition
  ------------------------------------------------------------
  Business definition: Sum of (MRR * 12) for all paying, non-internal
  accounts with at least one active subscription as of month end.

  Grain: one row per calendar month.
*/

with monthly as (

    select
        month_start as metric_month,
        account_id,
        mrr_usd
    from {{ ref('int_monthly_recurring_revenue') }}

),

agg as (

    select
        metric_month,
        sum(mrr_usd) * 12 as arr_usd,
        sum(mrr_usd) as mrr_usd,
        count(distinct account_id) as active_logo_count
    from monthly
    group by 1

),

with_lag as (

    select
        metric_month,
        mrr_usd,
        arr_usd,
        active_logo_count,
        lag(arr_usd) over (order by metric_month) as prior_month_arr_usd
    from agg

),

final as (

    select
        metric_month,
        mrr_usd,
        arr_usd,
        active_logo_count,
        prior_month_arr_usd,
        {{ safe_divide('arr_usd - prior_month_arr_usd', 'prior_month_arr_usd') }} as arr_mom_growth_rate,
        'arr' as metric_name,
        'Sum of active MRR * 12 for non-internal paying accounts' as metric_definition,
        {{ dbt.current_timestamp() }} as calculated_at

    from with_lag

)

select * from final
order by metric_month
