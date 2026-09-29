-- =============================================================================
-- Staging tables for synthetic source extracts (NO REAL PHI)
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS healthcare_demo_stg;

-- Patient identity fragments from multiple systems (entity resolution inputs)
CREATE TABLE IF NOT EXISTS healthcare_demo_stg.stg_patient_src_a (
    source_patient_id   VARCHAR(64)     NOT NULL,
    first_name          VARCHAR(64)     NOT NULL,   -- synthetic given names
    last_name           VARCHAR(64)     NOT NULL,
    birth_date          DATE            NOT NULL,
    sex_cd              CHAR(1)         NOT NULL,
    zip5                CHAR(5)         NOT NULL,   -- will be truncated to zip3
    phone_last4         CHAR(4),
    attributed_pcp_nk   VARCHAR(64),
    coverage_segment_cd VARCHAR(32),
    extract_ts          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_stg_patient_src_a PRIMARY KEY (source_patient_id)
);

CREATE TABLE IF NOT EXISTS healthcare_demo_stg.stg_patient_src_b (
    source_member_id    VARCHAR(64)     NOT NULL,
    given_nm            VARCHAR(64)     NOT NULL,
    family_nm           VARCHAR(64)     NOT NULL,
    dob                 DATE            NOT NULL,
    gender_cd           CHAR(1)         NOT NULL,
    postal_cd           CHAR(5)         NOT NULL,
    phone_last4         CHAR(4),
    pcp_id              VARCHAR(64),
    plan_segment        VARCHAR(32),
    extract_ts          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_stg_patient_src_b PRIMARY KEY (source_member_id)
);

CREATE TABLE IF NOT EXISTS healthcare_demo_stg.stg_provider (
    provider_nk         VARCHAR(64)     NOT NULL,
    npi_synthetic       VARCHAR(10)     NOT NULL,
    provider_name       VARCHAR(128)    NOT NULL,
    specialty_cd        VARCHAR(32)     NOT NULL,
    specialty_desc      VARCHAR(128)    NOT NULL,
    provider_type_cd    VARCHAR(32)     NOT NULL,
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    effective_start_dt  DATE            NOT NULL,
    CONSTRAINT pk_stg_provider PRIMARY KEY (provider_nk)
);

CREATE TABLE IF NOT EXISTS healthcare_demo_stg.stg_facility (
    facility_nk         VARCHAR(64)     NOT NULL,
    facility_name       VARCHAR(128)    NOT NULL,
    facility_type       VARCHAR(32)     NOT NULL,
    region_cd           VARCHAR(32)     NOT NULL,
    state_cd            CHAR(2)         NOT NULL,
    zip3                CHAR(3)         NOT NULL,
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    CONSTRAINT pk_stg_facility PRIMARY KEY (facility_nk)
);

CREATE TABLE IF NOT EXISTS healthcare_demo_stg.stg_diagnosis (
    icd10_cd            VARCHAR(8)      NOT NULL,
    icd10_desc          VARCHAR(256)    NOT NULL,
    chapter_cd          VARCHAR(8)      NOT NULL,
    chapter_desc        VARCHAR(128)    NOT NULL,
    clinical_group      VARCHAR(64)     NOT NULL,
    is_billable         BOOLEAN         NOT NULL DEFAULT TRUE,
    CONSTRAINT pk_stg_diagnosis PRIMARY KEY (icd10_cd)
);

CREATE TABLE IF NOT EXISTS healthcare_demo_stg.stg_encounters (
    encounter_nk            VARCHAR(64)     NOT NULL,
    source_patient_id       VARCHAR(64)     NOT NULL,
    provider_nk             VARCHAR(64)     NOT NULL,
    facility_nk             VARCHAR(64)     NOT NULL,
    primary_icd10_cd        VARCHAR(8)      NOT NULL,
    encounter_date          DATE            NOT NULL,
    discharge_date          DATE,
    encounter_type          VARCHAR(32)     NOT NULL,
    admission_type_cd       VARCHAR(32),
    discharge_disposition   VARCHAR(32),
    length_of_stay_days     INT             NOT NULL DEFAULT 0,
    total_charges_amt       NUMERIC(14, 2)  NOT NULL DEFAULT 0,
    is_readmit_30d          BOOLEAN         NOT NULL DEFAULT FALSE,
    CONSTRAINT pk_stg_encounters PRIMARY KEY (encounter_nk)
);

CREATE TABLE IF NOT EXISTS healthcare_demo_stg.stg_claims (
    claim_nk                VARCHAR(64)     NOT NULL,
    source_member_id        VARCHAR(64)     NOT NULL,  -- may map via entity resolution
    billing_provider_nk     VARCHAR(64)     NOT NULL,
    facility_nk             VARCHAR(64),
    primary_icd10_cd        VARCHAR(8)      NOT NULL,
    service_date            DATE            NOT NULL,
    paid_date               DATE,
    claim_type_cd           VARCHAR(32)     NOT NULL,
    claim_status            VARCHAR(32)     NOT NULL,
    place_of_service_cd     VARCHAR(8),
    billed_amt              NUMERIC(14, 2)  NOT NULL DEFAULT 0,
    allowed_amt             NUMERIC(14, 2)  NOT NULL DEFAULT 0,
    paid_amt                NUMERIC(14, 2)  NOT NULL DEFAULT 0,
    member_responsibility   NUMERIC(14, 2)  NOT NULL DEFAULT 0,
    CONSTRAINT pk_stg_claims PRIMARY KEY (claim_nk)
);

COMMENT ON SCHEMA healthcare_demo_stg IS
    'SYNTHETIC DEMO staging — no real PHI.';
