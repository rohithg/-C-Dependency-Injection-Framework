{{
  config(
    materialized='table',
    tags=['metrics', 'finance']
  )
}}

/*
  Logo Churn Rate — metrics-as-code definition
*/

with monthly as (

    select
        month_start,
        account_id,
        mrr_usd
    from {{ ref('int_monthly_recurring_revenue') }}

),

account_months as (

    select
        month_start,
        account_id,
        mrr_usd,
        lag(mrr_usd) over (
            partition by account_id
            order by month_start
        ) as prior_mrr_usd
    from monthly

),

churned as (

    select
        month_start as metric_month,
        count(distinct case
            when prior_mrr_usd > 0 and coalesce(mrr_usd, 0) = 0
            then account_id
        end) as churned_logos,
        count(distinct case
            when prior_mrr_usd > 0
            then account_id
        end) as beginning_logos
    from account_months
    group by 1

),

final as (

    select
        metric_month,
        beginning_logos,
        churned_logos,
        {{ safe_divide('churned_logos', 'beginning_logos') }} as logo_churn_rate,
        'logo_churn' as metric_name,
        'Churned logos / logos with MRR in prior month' as metric_definition,
        {{ dbt.current_timestamp() }} as calculated_at

    from churned
    where beginning_logos > 0

)

select * from final
order by metric_month
