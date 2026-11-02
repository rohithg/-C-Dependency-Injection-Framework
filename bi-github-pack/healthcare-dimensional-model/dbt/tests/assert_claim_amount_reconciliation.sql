-- Singular test: PAID claims — paid + member_responsibility ≈ allowed (± $1)

select
    claim_nk,
    allowed_amt,
    paid_amt,
    member_responsibility,
    (paid_amt + member_responsibility) as paid_plus_resp
from {{ ref('fct_claims') }}
where claim_status = 'PAID'
  and abs((paid_amt + member_responsibility) - allowed_amt) > 1.00
