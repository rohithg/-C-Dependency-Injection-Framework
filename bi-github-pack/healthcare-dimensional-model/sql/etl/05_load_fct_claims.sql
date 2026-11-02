-- =============================================================================
-- 05_load_fct_claims.sql — claims fact load with SK lookups
-- SYNTHETIC DEMO ONLY — NO REAL PHI
-- =============================================================================

CREATE SEQUENCE IF NOT EXISTS healthcare_demo.seq_claim_sk START 80000;

INSERT INTO healthcare_demo.fct_claims (
    claim_sk,
    claim_nk,
    patient_sk,
    billing_provider_sk,
    facility_sk,
    primary_dx_sk,
    service_date_sk,
    paid_date_sk,
    claim_type_cd,
    claim_status,
    place_of_service_cd,
    billed_amt,
    allowed_amt,
    paid_amt,
    member_responsibility,
    source_system_cd,
    loaded_at
)
SELECT
    NEXTVAL('healthcare_demo.seq_claim_sk'),
    c.claim_nk,
    p.patient_sk,
    pr.provider_sk,
    f.facility_sk,
    d.diagnosis_sk,
    dd_svc.date_sk                                                      AS service_date_sk,
    dd_paid.date_sk                                                     AS paid_date_sk,
    c.claim_type_cd,
    c.claim_status,
    c.place_of_service_cd,
    c.billed_amt,
    c.allowed_amt,
    c.paid_amt,
    c.member_responsibility,
    'RCM_CLM',
    CURRENT_TIMESTAMP
FROM healthcare_demo_stg.stg_claims c
JOIN healthcare_demo_stg.stg_empi_crosswalk x
    ON x.source_system_cd = 'RCM_CLM'
   AND x.source_patient_id = c.source_member_id
JOIN healthcare_demo.dim_patient p
    ON p.enterprise_patient_id = x.enterprise_patient_id
   AND p.is_current = TRUE
JOIN healthcare_demo.dim_provider pr
    ON pr.provider_nk = c.billing_provider_nk
LEFT JOIN healthcare_demo.dim_facility f
    ON f.facility_nk = c.facility_nk
JOIN healthcare_demo.dim_diagnosis d
    ON d.icd10_cd = c.primary_icd10_cd
JOIN healthcare_demo.dim_date dd_svc
    ON dd_svc.full_date = c.service_date
LEFT JOIN healthcare_demo.dim_date dd_paid
    ON dd_paid.full_date = c.paid_date
ON CONFLICT (claim_nk) DO UPDATE SET
    patient_sk            = EXCLUDED.patient_sk,
    billing_provider_sk   = EXCLUDED.billing_provider_sk,
    facility_sk           = EXCLUDED.facility_sk,
    primary_dx_sk         = EXCLUDED.primary_dx_sk,
    service_date_sk       = EXCLUDED.service_date_sk,
    paid_date_sk          = EXCLUDED.paid_date_sk,
    claim_type_cd         = EXCLUDED.claim_type_cd,
    claim_status          = EXCLUDED.claim_status,
    place_of_service_cd   = EXCLUDED.place_of_service_cd,
    billed_amt            = EXCLUDED.billed_amt,
    allowed_amt           = EXCLUDED.allowed_amt,
    paid_amt              = EXCLUDED.paid_amt,
    member_responsibility = EXCLUDED.member_responsibility,
    loaded_at             = CURRENT_TIMESTAMP;
