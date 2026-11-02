-- =============================================================================
-- dim_facility — care delivery location (SYNTHETIC DEMO ONLY)
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS healthcare_demo;

CREATE TABLE IF NOT EXISTS healthcare_demo.dim_facility (
    facility_sk         BIGINT          NOT NULL,
    facility_nk         VARCHAR(64)     NOT NULL,
    facility_name       VARCHAR(128)    NOT NULL,
    facility_type       VARCHAR(32)     NOT NULL,   -- HOSPITAL, CLINIC, ASC, VIRTUAL
    region_cd           VARCHAR(32)     NOT NULL,
    state_cd            CHAR(2)         NOT NULL,
    zip3                CHAR(3)         NOT NULL,
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_dim_facility PRIMARY KEY (facility_sk),
    CONSTRAINT uq_dim_facility_nk UNIQUE (facility_nk),
    CONSTRAINT chk_dim_facility_type CHECK (
        facility_type IN ('HOSPITAL', 'CLINIC', 'ASC', 'VIRTUAL', 'URGENT_CARE')
    )
);

COMMENT ON TABLE healthcare_demo.dim_facility IS
    'SYNTHETIC DEMO — facility dimension.';
