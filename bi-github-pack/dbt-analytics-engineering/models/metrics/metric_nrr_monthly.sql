{{
  config(
    materialized='table',
    tags=['metrics', 'finance']
  )
}}

/*
  Net Revenue Retention (NRR) — metrics-as-code definition
*/

with monthly as (

    select
        month_start,
        account_id,
        mrr_usd
    from {{ ref('int_monthly_recurring_revenue') }}

),

with_lag as (

    select
        month_start as metric_month,
        account_id,
        mrr_usd as ending_mrr_usd,
        lag(mrr_usd) over (
            partition by account_id
            order by month_start
        ) as beginning_mrr_usd
    from monthly

),

cohort as (

    select
        metric_month,
        sum(beginning_mrr_usd) as beginning_mrr_usd,
        sum(case
            when beginning_mrr_usd > 0 then ending_mrr_usd
            else 0
        end) as ending_cohort_mrr_usd
    from with_lag
    where beginning_mrr_usd > 0
    group by 1

),

final as (

    select
        metric_month,
        beginning_mrr_usd,
        ending_cohort_mrr_usd,
        ending_cohort_mrr_usd - beginning_mrr_usd as net_mrr_change_usd,
        {{ safe_divide('ending_cohort_mrr_usd', 'beginning_mrr_usd') }} as nrr,
        'nrr' as metric_name,
        'Ending MRR of prior-month cohort / beginning MRR' as metric_definition,
        {{ dbt.current_timestamp() }} as calculated_at

    from cohort

)

select * from final
order by metric_month
