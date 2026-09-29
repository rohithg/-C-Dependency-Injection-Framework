/*
  Business question: How is Net Revenue Retention trending month over month,
  and which months show net expansion (NRR > 1)?

  Audience: Finance / Executive
  Metrics used: metric_nrr_monthly, metric_logo_churn_monthly, metric_arr_monthly
*/

select
    n.metric_month,
    n.beginning_mrr_usd,
    n.ending_cohort_mrr_usd,
    n.net_mrr_change_usd,
    round(n.nrr, 3) as nrr,
    case when n.nrr >= 1 then 'expansion' else 'contraction' end as nrr_signal,
    round(c.logo_churn_rate, 3) as logo_churn_rate,
    a.arr_usd as ending_arr_usd,
    a.active_logo_count
from {{ ref('metric_nrr_monthly') }} n
left join {{ ref('metric_logo_churn_monthly') }} c
    on n.metric_month = c.metric_month
left join {{ ref('metric_arr_monthly') }} a
    on n.metric_month = a.metric_month
order by n.metric_month
