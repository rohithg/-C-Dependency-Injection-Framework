-- =============================================================================
-- dim_provider — provider dimension (SYNTHETIC DEMO ONLY)
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS healthcare_demo;

CREATE TABLE IF NOT EXISTS healthcare_demo.dim_provider (
    provider_sk         BIGINT          NOT NULL,
    provider_nk         VARCHAR(64)     NOT NULL,
    npi_synthetic       VARCHAR(10)     NOT NULL,   -- 10-digit synthetic NPI-like id
    provider_name       VARCHAR(128)    NOT NULL,
    specialty_cd        VARCHAR(32)     NOT NULL,
    specialty_desc      VARCHAR(128)    NOT NULL,
    provider_type_cd    VARCHAR(32)     NOT NULL,   -- MD, DO, NP, PA, etc.
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    effective_start_dt  DATE            NOT NULL,
    created_at          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_dim_provider PRIMARY KEY (provider_sk),
    CONSTRAINT uq_dim_provider_nk UNIQUE (provider_nk),
    CONSTRAINT chk_dim_provider_npi CHECK (npi_synthetic ~ '^[0-9]{10}$')
);

COMMENT ON TABLE healthcare_demo.dim_provider IS
    'SYNTHETIC DEMO — provider dimension. Synthetic NPIs only.';
