/*
  Singular test: NRR should be non-negative when beginning MRR > 0.
  Soft upper bound (5.0) catches unit errors (e.g. mixing cents and dollars).
*/

select
    metric_month,
    beginning_mrr_usd,
    ending_cohort_mrr_usd,
    nrr
from {{ ref('metric_nrr_monthly') }}
where nrr < 0
   or nrr > 5.0
   or beginning_mrr_usd <= 0
