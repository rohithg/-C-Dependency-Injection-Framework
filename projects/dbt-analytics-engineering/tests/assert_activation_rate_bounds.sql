/*
  Singular test: Activation rate must be between 0 and 1.
  Invariant: accounts_activated <= accounts_started.
*/

select
    as_of_date,
    grain,
    cohort_month,
    accounts_started,
    accounts_activated,
    activation_rate
from {{ ref('metric_activation_rate') }}
where activation_rate < 0
   or activation_rate > 1
   or accounts_activated > accounts_started
   or accounts_started < 0
