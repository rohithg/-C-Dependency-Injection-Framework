-- =============================================================================
-- DQ: Valid dates — chronology and calendar membership
-- Expectation: each query returns 0 rows
-- =============================================================================

-- Discharge before encounter
SELECT
    'enc_discharge_before_admit' AS test_name,
    e.encounter_nk,
    e.encounter_date_sk,
    e.discharge_date_sk
FROM healthcare_demo.fct_encounters e
WHERE e.discharge_date_sk IS NOT NULL
  AND e.discharge_date_sk < e.encounter_date_sk;

-- Paid date before service date
SELECT
    'clm_paid_before_service' AS test_name,
    c.claim_nk,
    c.service_date_sk,
    c.paid_date_sk
FROM healthcare_demo.fct_claims c
WHERE c.paid_date_sk IS NOT NULL
  AND c.paid_date_sk < c.service_date_sk;

-- LOS inconsistent with date span (inpatient)
SELECT
    'enc_los_mismatch' AS test_name,
    e.encounter_nk,
    e.length_of_stay_days,
    (d_out.full_date - d_in.full_date) AS calendar_span_days
FROM healthcare_demo.fct_encounters e
JOIN healthcare_demo.dim_date d_in  ON d_in.date_sk = e.encounter_date_sk
JOIN healthcare_demo.dim_date d_out ON d_out.date_sk = e.discharge_date_sk
WHERE e.encounter_type = 'IP'
  AND e.length_of_stay_days <> (d_out.full_date - d_in.full_date);

-- Future encounter dates (relative to as-of demo clock)
SELECT
    'enc_future_date' AS test_name,
    e.encounter_nk,
    d.full_date
FROM healthcare_demo.fct_encounters e
JOIN healthcare_demo.dim_date d ON d.date_sk = e.encounter_date_sk
WHERE d.full_date > CURRENT_DATE;

-- Patient effective window invalid
SELECT
    'patient_effective_window' AS test_name,
    p.patient_sk,
    p.effective_start_dt,
    p.effective_end_dt
FROM healthcare_demo.dim_patient p
WHERE p.effective_end_dt IS NOT NULL
  AND p.effective_end_dt < p.effective_start_dt;
