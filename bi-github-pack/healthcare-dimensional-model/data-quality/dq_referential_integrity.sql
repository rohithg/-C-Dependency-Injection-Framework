-- =============================================================================
-- DQ: Referential integrity — facts must resolve to dimensions
-- Expectation: each query returns 0 rows
-- SYNTHETIC DEMO ONLY
-- =============================================================================

-- Encounters → patient
SELECT 'fct_encounters.patient_sk' AS test_name, e.encounter_nk, e.patient_sk
FROM healthcare_demo.fct_encounters e
LEFT JOIN healthcare_demo.dim_patient p ON p.patient_sk = e.patient_sk
WHERE p.patient_sk IS NULL;

-- Encounters → provider
SELECT 'fct_encounters.provider_sk' AS test_name, e.encounter_nk, e.provider_sk
FROM healthcare_demo.fct_encounters e
LEFT JOIN healthcare_demo.dim_provider p ON p.provider_sk = e.provider_sk
WHERE p.provider_sk IS NULL;

-- Encounters → facility
SELECT 'fct_encounters.facility_sk' AS test_name, e.encounter_nk, e.facility_sk
FROM healthcare_demo.fct_encounters e
LEFT JOIN healthcare_demo.dim_facility f ON f.facility_sk = e.facility_sk
WHERE f.facility_sk IS NULL;

-- Encounters → diagnosis
SELECT 'fct_encounters.primary_dx_sk' AS test_name, e.encounter_nk, e.primary_dx_sk
FROM healthcare_demo.fct_encounters e
LEFT JOIN healthcare_demo.dim_diagnosis d ON d.diagnosis_sk = e.primary_dx_sk
WHERE d.diagnosis_sk IS NULL;

-- Encounters → date
SELECT 'fct_encounters.encounter_date_sk' AS test_name, e.encounter_nk, e.encounter_date_sk
FROM healthcare_demo.fct_encounters e
LEFT JOIN healthcare_demo.dim_date d ON d.date_sk = e.encounter_date_sk
WHERE d.date_sk IS NULL;

-- Claims → patient
SELECT 'fct_claims.patient_sk' AS test_name, c.claim_nk, c.patient_sk
FROM healthcare_demo.fct_claims c
LEFT JOIN healthcare_demo.dim_patient p ON p.patient_sk = c.patient_sk
WHERE p.patient_sk IS NULL;

-- Claims → billing provider
SELECT 'fct_claims.billing_provider_sk' AS test_name, c.claim_nk, c.billing_provider_sk
FROM healthcare_demo.fct_claims c
LEFT JOIN healthcare_demo.dim_provider p ON p.provider_sk = c.billing_provider_sk
WHERE p.provider_sk IS NULL;

-- Claims → diagnosis
SELECT 'fct_claims.primary_dx_sk' AS test_name, c.claim_nk, c.primary_dx_sk
FROM healthcare_demo.fct_claims c
LEFT JOIN healthcare_demo.dim_diagnosis d ON d.diagnosis_sk = c.primary_dx_sk
WHERE d.diagnosis_sk IS NULL;

-- Claims → service date
SELECT 'fct_claims.service_date_sk' AS test_name, c.claim_nk, c.service_date_sk
FROM healthcare_demo.fct_claims c
LEFT JOIN healthcare_demo.dim_date d ON d.date_sk = c.service_date_sk
WHERE d.date_sk IS NULL;
