-- =============================================================================
-- DQ: SCD Type 2 integrity on dim_patient
-- Expectation: each query returns 0 rows
-- =============================================================================

-- More than one current row per enterprise patient
SELECT
    'scd2_multiple_current' AS test_name,
    p.enterprise_patient_id,
    COUNT(*) AS current_row_cnt
FROM healthcare_demo.dim_patient p
WHERE p.is_current = TRUE
GROUP BY p.enterprise_patient_id
HAVING COUNT(*) > 1;

-- Current row must have NULL end date
SELECT
    'scd2_current_has_end' AS test_name,
    p.patient_sk,
    p.enterprise_patient_id,
    p.effective_end_dt
FROM healthcare_demo.dim_patient p
WHERE p.is_current = TRUE
  AND p.effective_end_dt IS NOT NULL;

-- Historical row must have end date
SELECT
    'scd2_history_missing_end' AS test_name,
    p.patient_sk,
    p.enterprise_patient_id
FROM healthcare_demo.dim_patient p
WHERE p.is_current = FALSE
  AND p.effective_end_dt IS NULL;

-- Overlapping effective windows for same enterprise patient
SELECT
    'scd2_overlapping_windows' AS test_name,
    a.enterprise_patient_id,
    a.patient_sk AS patient_sk_a,
    b.patient_sk AS patient_sk_b,
    a.effective_start_dt AS start_a,
    a.effective_end_dt   AS end_a,
    b.effective_start_dt AS start_b,
    b.effective_end_dt   AS end_b
FROM healthcare_demo.dim_patient a
JOIN healthcare_demo.dim_patient b
  ON a.enterprise_patient_id = b.enterprise_patient_id
 AND a.patient_sk < b.patient_sk
 AND a.effective_start_dt <= COALESCE(b.effective_end_dt, DATE '9999-12-31')
 AND b.effective_start_dt <= COALESCE(a.effective_end_dt, DATE '9999-12-31');
