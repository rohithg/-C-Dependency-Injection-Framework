-- =============================================================================
-- 03_load_reference_dims.sql — provider, facility, diagnosis (Type 1)
-- SYNTHETIC DEMO ONLY
-- =============================================================================

CREATE SEQUENCE IF NOT EXISTS healthcare_demo.seq_provider_sk START 2000;
CREATE SEQUENCE IF NOT EXISTS healthcare_demo.seq_facility_sk START 3000;
CREATE SEQUENCE IF NOT EXISTS healthcare_demo.seq_diagnosis_sk START 4000;

-- Providers (upsert on natural key)
INSERT INTO healthcare_demo.dim_provider (
    provider_sk,
    provider_nk,
    npi_synthetic,
    provider_name,
    specialty_cd,
    specialty_desc,
    provider_type_cd,
    is_active,
    effective_start_dt,
    created_at,
    updated_at
)
SELECT
    NEXTVAL('healthcare_demo.seq_provider_sk'),
    s.provider_nk,
    s.npi_synthetic,
    s.provider_name,
    s.specialty_cd,
    s.specialty_desc,
    s.provider_type_cd,
    s.is_active,
    s.effective_start_dt,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
FROM healthcare_demo_stg.stg_provider s
ON CONFLICT (provider_nk) DO UPDATE SET
    npi_synthetic    = EXCLUDED.npi_synthetic,
    provider_name    = EXCLUDED.provider_name,
    specialty_cd     = EXCLUDED.specialty_cd,
    specialty_desc   = EXCLUDED.specialty_desc,
    provider_type_cd = EXCLUDED.provider_type_cd,
    is_active        = EXCLUDED.is_active,
    updated_at       = CURRENT_TIMESTAMP;

-- Facilities
INSERT INTO healthcare_demo.dim_facility (
    facility_sk,
    facility_nk,
    facility_name,
    facility_type,
    region_cd,
    state_cd,
    zip3,
    is_active,
    created_at,
    updated_at
)
SELECT
    NEXTVAL('healthcare_demo.seq_facility_sk'),
    s.facility_nk,
    s.facility_name,
    s.facility_type,
    s.region_cd,
    s.state_cd,
    s.zip3,
    s.is_active,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
FROM healthcare_demo_stg.stg_facility s
ON CONFLICT (facility_nk) DO UPDATE SET
    facility_name = EXCLUDED.facility_name,
    facility_type = EXCLUDED.facility_type,
    region_cd     = EXCLUDED.region_cd,
    state_cd      = EXCLUDED.state_cd,
    zip3          = EXCLUDED.zip3,
    is_active     = EXCLUDED.is_active,
    updated_at    = CURRENT_TIMESTAMP;

-- Diagnosis codes
INSERT INTO healthcare_demo.dim_diagnosis (
    diagnosis_sk,
    icd10_cd,
    icd10_desc,
    chapter_cd,
    chapter_desc,
    clinical_group,
    is_billable,
    created_at
)
SELECT
    NEXTVAL('healthcare_demo.seq_diagnosis_sk'),
    s.icd10_cd,
    s.icd10_desc,
    s.chapter_cd,
    s.chapter_desc,
    s.clinical_group,
    s.is_billable,
    CURRENT_TIMESTAMP
FROM healthcare_demo_stg.stg_diagnosis s
ON CONFLICT (icd10_cd) DO UPDATE SET
    icd10_desc     = EXCLUDED.icd10_desc,
    chapter_cd     = EXCLUDED.chapter_cd,
    chapter_desc   = EXCLUDED.chapter_desc,
    clinical_group = EXCLUDED.clinical_group,
    is_billable    = EXCLUDED.is_billable;
