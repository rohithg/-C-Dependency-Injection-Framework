-- =============================================================================
-- 02_load_dim_patient_scd2.sql — SCD Type 2 merge for dim_patient
-- SYNTHETIC DEMO ONLY — NO REAL PHI
-- =============================================================================
-- Tracked attributes (row_hash inputs):
--   first/last name tokens, zip3, attributed_pcp_nk, coverage_segment_cd, sex_cd
-- When a tracked attribute changes for an enterprise_patient_id:
--   1) expire the current row (is_current=FALSE, effective_end_dt=day before change)
--   2) insert a new version with is_current=TRUE
-- =============================================================================

-- Step 0: ensure a sequence / sk generator exists
CREATE SEQUENCE IF NOT EXISTS healthcare_demo.seq_patient_sk START 1000;

-- Step 1: build a standardized staging view from resolved enterprise keys
-- (assumes entity-resolution output is available — see entity-resolution/)
CREATE OR REPLACE VIEW healthcare_demo_stg.v_patient_standardized AS
SELECT
    r.enterprise_patient_id,
    r.primary_source_patient_id                                         AS patient_nk,
    r.primary_source_system_cd                                          AS source_system_cd,
    -- Demo tokenization: SHA-256 hex truncated (irreversible stand-in)
    LEFT(ENCODE(SHA256(LOWER(TRIM(r.first_name))::BYTEA), 'hex'), 16) AS first_name_token,
    LEFT(ENCODE(SHA256(LOWER(TRIM(r.last_name))::BYTEA), 'hex'), 16)  AS last_name_token,
    r.birth_date,
    UPPER(r.sex_cd)                                                     AS sex_cd,
    LEFT(r.zip5, 3)                                                     AS zip3,
    r.attributed_pcp_nk,
    r.coverage_segment_cd,
    MD5(
        CONCAT_WS('|',
            LOWER(TRIM(r.first_name)),
            LOWER(TRIM(r.last_name)),
            LEFT(r.zip5, 3),
            COALESCE(r.attributed_pcp_nk, ''),
            COALESCE(r.coverage_segment_cd, ''),
            UPPER(r.sex_cd)
        )
    )                                                                   AS row_hash,
    CURRENT_DATE                                                        AS effective_start_dt
FROM healthcare_demo_stg.stg_empi_resolved r;

-- Step 2: expire changed current rows (SCD2 close-out)
UPDATE healthcare_demo.dim_patient AS tgt
SET
    is_current       = FALSE,
    effective_end_dt = staging.effective_start_dt - INTERVAL '1 day',
    updated_at       = CURRENT_TIMESTAMP
FROM healthcare_demo_stg.v_patient_standardized AS staging
WHERE tgt.enterprise_patient_id = staging.enterprise_patient_id
  AND tgt.is_current = TRUE
  AND tgt.row_hash <> staging.row_hash;

-- Step 3: insert new versions for new patients OR changed patients
INSERT INTO healthcare_demo.dim_patient (
    patient_sk,
    patient_nk,
    enterprise_patient_id,
    source_system_cd,
    first_name_token,
    last_name_token,
    birth_date,
    sex_cd,
    zip3,
    attributed_pcp_nk,
    coverage_segment_cd,
    effective_start_dt,
    effective_end_dt,
    is_current,
    row_hash,
    created_at,
    updated_at
)
SELECT
    NEXTVAL('healthcare_demo.seq_patient_sk'),
    s.patient_nk,
    s.enterprise_patient_id,
    s.source_system_cd,
    s.first_name_token,
    s.last_name_token,
    s.birth_date,
    s.sex_cd,
    s.zip3,
    s.attributed_pcp_nk,
    s.coverage_segment_cd,
    s.effective_start_dt,
    NULL,
    TRUE,
    s.row_hash,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
FROM healthcare_demo_stg.v_patient_standardized s
WHERE NOT EXISTS (
    SELECT 1
    FROM healthcare_demo.dim_patient d
    WHERE d.enterprise_patient_id = s.enterprise_patient_id
      AND d.is_current = TRUE
      AND d.row_hash = s.row_hash
);

-- Step 4: sanity — at most one current row per enterprise patient
-- (enforced by partial unique index; this query is for ETL logging)
-- SELECT enterprise_patient_id, COUNT(*)
-- FROM healthcare_demo.dim_patient
-- WHERE is_current
-- GROUP BY 1
-- HAVING COUNT(*) > 1;
