-- =============================================================================
-- dim_patient — SCD Type 2 patient dimension (SYNTHETIC DEMO ONLY — NO REAL PHI)
-- =============================================================================
-- Grain: one row per patient version. is_current marks the active version.
-- Identity is tokenized; do not store real MRNs or clear-text names in this repo.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS healthcare_demo;

CREATE TABLE IF NOT EXISTS healthcare_demo.dim_patient (
    patient_sk              BIGINT          NOT NULL,
    patient_nk              VARCHAR(64)     NOT NULL,   -- natural key from primary source (synthetic)
    enterprise_patient_id   VARCHAR(64)     NOT NULL,   -- resolved EMPI-style key (synthetic)
    source_system_cd        VARCHAR(32)     NOT NULL,   -- e.g. EHR_ENC, MPI_SRC_A
    first_name_token        VARCHAR(64)     NOT NULL,   -- irreversible demo token
    last_name_token         VARCHAR(64)     NOT NULL,
    birth_date              DATE            NOT NULL,   -- synthetic DOB
    sex_cd                  CHAR(1)         NOT NULL,   -- M/F/U/X
    zip3                    CHAR(3)         NOT NULL,   -- geographic band only
    attributed_pcp_nk       VARCHAR(64),                -- synthetic provider NK
    coverage_segment_cd     VARCHAR(32),                -- e.g. HMO, PPO, MEDICAID
    effective_start_dt      DATE            NOT NULL,
    effective_end_dt        DATE,                       -- NULL when current
    is_current              BOOLEAN         NOT NULL DEFAULT TRUE,
    row_hash                VARCHAR(64)     NOT NULL,   -- hash of tracked attributes
    created_at              TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_dim_patient PRIMARY KEY (patient_sk),
    CONSTRAINT chk_dim_patient_sex CHECK (sex_cd IN ('M', 'F', 'U', 'X')),
    CONSTRAINT chk_dim_patient_dates CHECK (
        effective_end_dt IS NULL OR effective_end_dt >= effective_start_dt
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_dim_patient_current
    ON healthcare_demo.dim_patient (enterprise_patient_id)
    WHERE is_current = TRUE;

CREATE INDEX IF NOT EXISTS ix_dim_patient_nk
    ON healthcare_demo.dim_patient (patient_nk);

COMMENT ON TABLE healthcare_demo.dim_patient IS
    'SYNTHETIC DEMO — SCD2 patient dimension. No real PHI.';
