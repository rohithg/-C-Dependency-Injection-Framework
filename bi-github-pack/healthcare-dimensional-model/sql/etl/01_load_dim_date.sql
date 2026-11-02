-- =============================================================================
-- 01_load_dim_date.sql — populate conformed date dimension
-- Demo range: 2023-01-01 through 2025-12-31
-- Dialect: PostgreSQL-compatible (generate_series). Adapt for Snowflake/BQ.
-- =============================================================================

INSERT INTO healthcare_demo.dim_date (
    date_sk,
    full_date,
    day_of_week,
    day_name,
    day_of_month,
    day_of_year,
    week_of_year,
    month_num,
    month_name,
    quarter_num,
    year_num,
    is_weekend,
    is_month_end,
    fiscal_year,
    fiscal_quarter
)
SELECT
    CAST(TO_CHAR(d, 'YYYYMMDD') AS INT)                          AS date_sk,
    d::DATE                                                       AS full_date,
    CAST(EXTRACT(ISODOW FROM d) AS SMALLINT)                      AS day_of_week,
    TO_CHAR(d, 'Day')                                             AS day_name,
    CAST(EXTRACT(DAY FROM d) AS SMALLINT)                         AS day_of_month,
    CAST(EXTRACT(DOY FROM d) AS SMALLINT)                         AS day_of_year,
    CAST(EXTRACT(WEEK FROM d) AS SMALLINT)                        AS week_of_year,
    CAST(EXTRACT(MONTH FROM d) AS SMALLINT)                       AS month_num,
    TO_CHAR(d, 'Month')                                           AS month_name,
    CAST(EXTRACT(QUARTER FROM d) AS SMALLINT)                     AS quarter_num,
    CAST(EXTRACT(YEAR FROM d) AS INT)                             AS year_num,
    EXTRACT(ISODOW FROM d) IN (6, 7)                              AS is_weekend,
    d = (DATE_TRUNC('month', d) + INTERVAL '1 month - 1 day')::DATE AS is_month_end,
    CAST(EXTRACT(YEAR FROM d) AS INT)                             AS fiscal_year,
    CAST(EXTRACT(QUARTER FROM d) AS SMALLINT)                     AS fiscal_quarter
FROM generate_series(DATE '2023-01-01', DATE '2025-12-31', INTERVAL '1 day') AS d
ON CONFLICT (date_sk) DO NOTHING;
