/*
  Business question: Which signup cohorts activate within 14 days,
  and how does activation correlate with eventual paid conversion?

  Audience: Product / Growth
  Marts used: dim_accounts, fct_subscriptions, metric_activation_rate
*/

with activation as (

    select
        cohort_month,
        accounts_started,
        accounts_activated,
        activation_rate
    from {{ ref('metric_activation_rate') }}
    where grain = 'signup_month'

),

paid as (

    select
        date_trunc('month', a.account_created_at) as cohort_month,
        count(distinct a.account_id) as accounts_with_paid_sub
    from {{ ref('dim_accounts') }} a
    inner join {{ ref('fct_subscriptions') }} s
        on a.account_id = s.account_id
    where not a.is_internal
      and s.mrr_usd > 0
      and s.status in ('active', 'churned', 'upgraded')
    group by 1

)

select
    act.cohort_month,
    act.accounts_started,
    act.accounts_activated,
    act.activation_rate,
    coalesce(p.accounts_with_paid_sub, 0) as accounts_with_paid_sub,
    round(
        coalesce(p.accounts_with_paid_sub, 0)
        / nullif(act.accounts_started, 0),
        3
    ) as paid_conversion_rate
from activation act
left join paid p
    on act.cohort_month = p.cohort_month
order by act.cohort_month
