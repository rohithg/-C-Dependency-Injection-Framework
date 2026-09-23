-- =============================================================================
-- fct_claims — claim header fact (SYNTHETIC DEMO ONLY — NO REAL PHI)
-- Grain: one row per claim header
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS healthcare_demo;

CREATE TABLE IF NOT EXISTS healthcare_demo.fct_claims (
    claim_sk                BIGINT          NOT NULL,
    claim_nk                VARCHAR(64)     NOT NULL,   -- synthetic claim id
    patient_sk              BIGINT          NOT NULL,
    billing_provider_sk     BIGINT          NOT NULL,
    facility_sk             BIGINT,
    primary_dx_sk           BIGINT          NOT NULL,
    service_date_sk         INT             NOT NULL,
    paid_date_sk            INT,
    claim_type_cd           VARCHAR(32)     NOT NULL,   -- PROF, INST, RX
    claim_status            VARCHAR(32)     NOT NULL,   -- PAID, DENIED, PENDING, REJECTED
    place_of_service_cd     VARCHAR(8),
    billed_amt              NUMERIC(14, 2)  NOT NULL DEFAULT 0,
    allowed_amt             NUMERIC(14, 2)  NOT NULL DEFAULT 0,
    paid_amt                NUMERIC(14, 2)  NOT NULL DEFAULT 0,
    member_responsibility   NUMERIC(14, 2)  NOT NULL DEFAULT 0,
    source_system_cd        VARCHAR(32)     NOT NULL DEFAULT 'RCM_CLM',
    loaded_at               TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_fct_claims PRIMARY KEY (claim_sk),
    CONSTRAINT uq_fct_claims_nk UNIQUE (claim_nk),
    CONSTRAINT fk_clm_patient FOREIGN KEY (patient_sk)
        REFERENCES healthcare_demo.dim_patient (patient_sk),
    CONSTRAINT fk_clm_provider FOREIGN KEY (billing_provider_sk)
        REFERENCES healthcare_demo.dim_provider (provider_sk),
    CONSTRAINT fk_clm_facility FOREIGN KEY (facility_sk)
        REFERENCES healthcare_demo.dim_facility (facility_sk),
    CONSTRAINT fk_clm_diagnosis FOREIGN KEY (primary_dx_sk)
        REFERENCES healthcare_demo.dim_diagnosis (diagnosis_sk),
    CONSTRAINT fk_clm_svc_date FOREIGN KEY (service_date_sk)
        REFERENCES healthcare_demo.dim_date (date_sk),
    CONSTRAINT fk_clm_paid_date FOREIGN KEY (paid_date_sk)
        REFERENCES healthcare_demo.dim_date (date_sk),
    CONSTRAINT chk_clm_status CHECK (
        claim_status IN ('PAID', 'DENIED', 'PENDING', 'REJECTED', 'ADJUSTED')
    ),
    CONSTRAINT chk_clm_type CHECK (
        claim_type_cd IN ('PROF', 'INST', 'RX')
    ),
    CONSTRAINT chk_clm_amounts CHECK (
        billed_amt >= 0
        AND allowed_amt >= 0
        AND paid_amt >= 0
        AND member_responsibility >= 0
    )
);

CREATE INDEX IF NOT EXISTS ix_fct_claims_patient
    ON healthcare_demo.fct_claims (patient_sk);
CREATE INDEX IF NOT EXISTS ix_fct_claims_svc_date
    ON healthcare_demo.fct_claims (service_date_sk);
CREATE INDEX IF NOT EXISTS ix_fct_claims_status
    ON healthcare_demo.fct_claims (claim_status);

COMMENT ON TABLE healthcare_demo.fct_claims IS
    'SYNTHETIC DEMO — claims header fact. No real PHI.';
