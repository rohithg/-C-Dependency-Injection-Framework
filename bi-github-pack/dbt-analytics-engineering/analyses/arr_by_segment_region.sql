/*
  Business question: What is our current ARR by segment and region?

  Audience: Finance / RevOps
  Marts used: fct_subscriptions, dim_accounts
*/

select
    a.segment,
    a.region,
    count(distinct s.account_id) as paying_accounts,
    sum(s.mrr_usd) as mrr_usd,
    sum(s.arr_usd) as arr_usd,
    round(sum(s.arr_usd) / nullif(sum(sum(s.arr_usd)) over (), 0) * 100, 1) as pct_of_total_arr
from {{ ref('fct_subscriptions') }} s
inner join {{ ref('dim_accounts') }} a
    on s.account_id = a.account_id
where s.is_currently_active
  and not s.is_internal
  and s.mrr_usd > 0
group by 1, 2
order by arr_usd desc
