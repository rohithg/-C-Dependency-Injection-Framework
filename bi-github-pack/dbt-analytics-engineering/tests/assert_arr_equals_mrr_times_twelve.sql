/*
  Singular test: ARR must equal MRR * 12 for every month in metric_arr_monthly.
  Invariant: arr_usd = mrr_usd * 12 (within floating-point tolerance).
*/

select
    metric_month,
    mrr_usd,
    arr_usd,
    mrr_usd * 12 as expected_arr
from {{ ref('metric_arr_monthly') }}
where abs(arr_usd - (mrr_usd * 12)) > 0.01
