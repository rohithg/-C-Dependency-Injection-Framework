/*
  Business question: What are the top churn reasons and lost ARR,
  and which plan tiers churn most?

  Audience: Customer Success / Finance
  Marts used: fct_subscriptions
*/

select
    coalesce(churn_reason, 'unspecified') as churn_reason,
    plan_tier,
    count(*) as churned_subscriptions,
    sum(arr_usd) as lost_arr_usd,
    round(avg(tenure_days), 0) as avg_tenure_days
from {{ ref('fct_subscriptions') }}
where is_churned
  and not is_internal
group by 1, 2
order by lost_arr_usd desc
