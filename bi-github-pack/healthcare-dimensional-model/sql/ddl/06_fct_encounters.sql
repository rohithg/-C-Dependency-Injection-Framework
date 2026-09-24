-- =============================================================================
-- fct_encounters — clinical encounter fact (SYNTHETIC DEMO ONLY — NO REAL PHI)
-- Grain: one row per encounter
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS healthcare_demo;

CREATE TABLE IF NOT EXISTS healthcare_demo.fct_encounters (
    encounter_sk            BIGINT          NOT NULL,
    encounter_nk            VARCHAR(64)     NOT NULL,   -- source encounter id (synthetic)
    patient_sk              BIGINT          NOT NULL,
    provider_sk             BIGINT          NOT NULL,
    facility_sk             BIGINT          NOT NULL,
    primary_dx_sk           BIGINT          NOT NULL,
    encounter_date_sk       INT             NOT NULL,
    discharge_date_sk       INT,                        -- NULL for ambulatory
    encounter_type          VARCHAR(32)     NOT NULL,   -- IP, OP, ED, TELEHEALTH
    admission_type_cd       VARCHAR(32),
    discharge_disposition   VARCHAR(32),
    length_of_stay_days     INT             NOT NULL DEFAULT 0,
    total_charges_amt       NUMERIC(14, 2)  NOT NULL DEFAULT 0,
    is_readmit_30d          BOOLEAN         NOT NULL DEFAULT FALSE,
    source_system_cd        VARCHAR(32)     NOT NULL DEFAULT 'EHR_ENC',
    loaded_at               TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_fct_encounters PRIMARY KEY (encounter_sk),
    CONSTRAINT uq_fct_encounters_nk UNIQUE (encounter_nk),
    CONSTRAINT fk_enc_patient FOREIGN KEY (patient_sk)
        REFERENCES healthcare_demo.dim_patient (patient_sk),
    CONSTRAINT fk_enc_provider FOREIGN KEY (provider_sk)
        REFERENCES healthcare_demo.dim_provider (provider_sk),
    CONSTRAINT fk_enc_facility FOREIGN KEY (facility_sk)
        REFERENCES healthcare_demo.dim_facility (facility_sk),
    CONSTRAINT fk_enc_diagnosis FOREIGN KEY (primary_dx_sk)
        REFERENCES healthcare_demo.dim_diagnosis (diagnosis_sk),
    CONSTRAINT fk_enc_date FOREIGN KEY (encounter_date_sk)
        REFERENCES healthcare_demo.dim_date (date_sk),
    CONSTRAINT fk_enc_discharge_date FOREIGN KEY (discharge_date_sk)
        REFERENCES healthcare_demo.dim_date (date_sk),
    CONSTRAINT chk_enc_type CHECK (
        encounter_type IN ('IP', 'OP', 'ED', 'TELEHEALTH', 'URGENT')
    ),
    CONSTRAINT chk_enc_los CHECK (length_of_stay_days >= 0),
    CONSTRAINT chk_enc_charges CHECK (total_charges_amt >= 0)
);

CREATE INDEX IF NOT EXISTS ix_fct_encounters_patient
    ON healthcare_demo.fct_encounters (patient_sk);
CREATE INDEX IF NOT EXISTS ix_fct_encounters_date
    ON healthcare_demo.fct_encounters (encounter_date_sk);
CREATE INDEX IF NOT EXISTS ix_fct_encounters_dx
    ON healthcare_demo.fct_encounters (primary_dx_sk);

COMMENT ON TABLE healthcare_demo.fct_encounters IS
    'SYNTHETIC DEMO — encounter fact. No real PHI.';
