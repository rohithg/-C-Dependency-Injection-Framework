/*
  Singular test: Logo churn rate must be between 0 and 1 inclusive.
  Invariant: 0 <= logo_churn_rate <= 1 when beginning_logos > 0.
*/

select
    metric_month,
    beginning_logos,
    churned_logos,
    logo_churn_rate
from {{ ref('metric_logo_churn_monthly') }}
where logo_churn_rate < 0
   or logo_churn_rate > 1
   or churned_logos > beginning_logos
