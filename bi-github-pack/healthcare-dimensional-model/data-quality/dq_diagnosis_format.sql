-- =============================================================================
-- DQ: Diagnosis code format & coverage
-- ICD-10-CM pattern (simplified): letter + 2 alnum + optional decimal + 1-4
-- Expectation: each query returns 0 rows
-- =============================================================================

-- Format violations in dim_diagnosis
SELECT
    'dim_diagnosis_icd10_format' AS test_name,
    d.diagnosis_sk,
    d.icd10_cd
FROM healthcare_demo.dim_diagnosis d
WHERE d.icd10_cd !~ '^[A-TV-Z][0-9][0-9A-Z](\.[0-9A-Z]{1,4})?$';

-- Staging encounters with unknown / malformed diagnosis codes
SELECT
    'stg_enc_unknown_dx' AS test_name,
    e.encounter_nk,
    e.primary_icd10_cd
FROM healthcare_demo_stg.stg_encounters e
LEFT JOIN healthcare_demo.dim_diagnosis d
    ON d.icd10_cd = e.primary_icd10_cd
WHERE d.diagnosis_sk IS NULL
   OR e.primary_icd10_cd !~ '^[A-TV-Z][0-9][0-9A-Z](\.[0-9A-Z]{1,4})?$';

-- Staging claims with unknown / malformed diagnosis codes
SELECT
    'stg_clm_unknown_dx' AS test_name,
    c.claim_nk,
    c.primary_icd10_cd
FROM healthcare_demo_stg.stg_claims c
LEFT JOIN healthcare_demo.dim_diagnosis d
    ON d.icd10_cd = c.primary_icd10_cd
WHERE d.diagnosis_sk IS NULL
   OR c.primary_icd10_cd !~ '^[A-TV-Z][0-9][0-9A-Z](\.[0-9A-Z]{1,4})?$';
