-- =============================================================================
-- dim_date — conformed calendar dimension
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS healthcare_demo;

CREATE TABLE IF NOT EXISTS healthcare_demo.dim_date (
    date_sk             INT             NOT NULL,   -- YYYYMMDD
    full_date           DATE            NOT NULL,
    day_of_week         SMALLINT        NOT NULL,   -- 1=Mon .. 7=Sun
    day_name            VARCHAR(16)     NOT NULL,
    day_of_month        SMALLINT        NOT NULL,
    day_of_year         SMALLINT        NOT NULL,
    week_of_year        SMALLINT        NOT NULL,
    month_num           SMALLINT        NOT NULL,
    month_name          VARCHAR(16)     NOT NULL,
    quarter_num         SMALLINT        NOT NULL,
    year_num            INT             NOT NULL,
    is_weekend          BOOLEAN         NOT NULL,
    is_month_end        BOOLEAN         NOT NULL,
    fiscal_year         INT             NOT NULL,   -- demo: FY = calendar year
    fiscal_quarter      SMALLINT        NOT NULL,
    CONSTRAINT pk_dim_date PRIMARY KEY (date_sk),
    CONSTRAINT uq_dim_date_full UNIQUE (full_date)
);

COMMENT ON TABLE healthcare_demo.dim_date IS
    'Conformed date dimension for encounter and claim date roles.';
