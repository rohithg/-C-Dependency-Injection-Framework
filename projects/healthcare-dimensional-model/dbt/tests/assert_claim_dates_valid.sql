-- Singular test: paid date must not precede service date

select
    claim_nk,
    service_date,
    paid_date
from {{ ref('fct_claims') }}
where paid_date is not null
  and paid_date < service_date
