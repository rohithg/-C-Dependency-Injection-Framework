-- =============================================================================
-- DQ: Claims amount integrity
-- Expectation: each query returns 0 rows (or within documented tolerance)
-- =============================================================================

-- Negative amounts
SELECT
    'clm_negative_amounts' AS test_name,
    c.claim_nk,
    c.billed_amt,
    c.allowed_amt,
    c.paid_amt,
    c.member_responsibility
FROM healthcare_demo.fct_claims c
WHERE c.billed_amt < 0
   OR c.allowed_amt < 0
   OR c.paid_amt < 0
   OR c.member_responsibility < 0;

-- Allowed should not exceed billed (common rule; adjust for contractual quirks)
SELECT
    'clm_allowed_gt_billed' AS test_name,
    c.claim_nk,
    c.billed_amt,
    c.allowed_amt
FROM healthcare_demo.fct_claims c
WHERE c.allowed_amt > c.billed_amt + 0.01;

-- Paid + member responsibility should approximate allowed (± $1.00)
SELECT
    'clm_paid_plus_resp_vs_allowed' AS test_name,
    c.claim_nk,
    c.allowed_amt,
    c.paid_amt,
    c.member_responsibility,
    (c.paid_amt + c.member_responsibility) AS paid_plus_resp
FROM healthcare_demo.fct_claims c
WHERE c.claim_status = 'PAID'
  AND ABS((c.paid_amt + c.member_responsibility) - c.allowed_amt) > 1.00;

-- Denied claims should have zero paid amount
SELECT
    'clm_denied_with_payment' AS test_name,
    c.claim_nk,
    c.claim_status,
    c.paid_amt
FROM healthcare_demo.fct_claims c
WHERE c.claim_status IN ('DENIED', 'REJECTED')
  AND c.paid_amt <> 0;
