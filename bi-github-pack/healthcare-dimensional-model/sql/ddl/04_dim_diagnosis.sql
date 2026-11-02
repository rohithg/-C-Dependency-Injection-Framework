-- =============================================================================
-- dim_diagnosis — ICD-10 diagnosis conformed dimension (SYNTHETIC / PUBLIC CODES)
-- =============================================================================
-- ICD-10-CM codes are a public code set. Descriptions here are abbreviated
-- for demo purposes and are not a complete clinical codebook.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS healthcare_demo;

CREATE TABLE IF NOT EXISTS healthcare_demo.dim_diagnosis (
    diagnosis_sk        BIGINT          NOT NULL,
    icd10_cd            VARCHAR(8)      NOT NULL,   -- e.g. E11.9, J06.9
    icd10_desc          VARCHAR(256)    NOT NULL,
    chapter_cd          VARCHAR(8)      NOT NULL,   -- e.g. E00-E89
    chapter_desc        VARCHAR(128)    NOT NULL,
    clinical_group      VARCHAR(64)     NOT NULL,   -- e.g. Diabetes, Respiratory
    is_billable         BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_dim_diagnosis PRIMARY KEY (diagnosis_sk),
    CONSTRAINT uq_dim_diagnosis_icd10 UNIQUE (icd10_cd),
    CONSTRAINT chk_dim_diagnosis_icd10_format CHECK (
        icd10_cd ~ '^[A-TV-Z][0-9][0-9A-Z](\.[0-9A-Z]{1,4})?$'
    )
);

COMMENT ON TABLE healthcare_demo.dim_diagnosis IS
    'SYNTHETIC DEMO — ICD-10 diagnosis dimension (abbreviated public codes).';
