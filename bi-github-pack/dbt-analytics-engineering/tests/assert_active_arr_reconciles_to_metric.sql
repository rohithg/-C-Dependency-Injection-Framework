/*
  Singular test: Active subscription ARR in the fact should reconcile to the
  latest month in metric_arr_monthly (metrics-as-code consistency).
*/

with fact_arr as (

    select
        sum(arr_usd) as fact_arr_usd
    from {{ ref('fct_subscriptions') }}
    where is_currently_active
      and not is_internal
      and mrr_usd > 0

),

metric_arr as (

    select
        arr_usd as metric_arr_usd
    from {{ ref('metric_arr_monthly') }}
    order by metric_month desc
    limit 1

)

select
    f.fact_arr_usd,
    m.metric_arr_usd
from fact_arr f
cross join metric_arr m
where abs(f.fact_arr_usd - m.metric_arr_usd) > 0.01
