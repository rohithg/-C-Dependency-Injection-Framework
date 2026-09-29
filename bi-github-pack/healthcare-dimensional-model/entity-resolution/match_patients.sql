-- =============================================================================
-- Entity resolution: match patients across EHR + Claims (SYNTHETIC DEMO ONLY)
-- =============================================================================
-- Creates supporting tables, runs deterministic linking, then a simplified
-- probabilistic score for residual pairs. Not production-ready MPI software.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS healthcare_demo_stg;

CREATE TABLE IF NOT EXISTS healthcare_demo_stg.stg_empi_crosswalk (
    source_system_cd        VARCHAR(32)     NOT NULL,
    source_patient_id       VARCHAR(64)     NOT NULL,
    enterprise_patient_id   VARCHAR(64)     NOT NULL,
    match_rule_cd           VARCHAR(32)     NOT NULL,  -- R1, R2, R3, PROB, NEW
    match_score             NUMERIC(5, 3),
    linked_at               TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_stg_empi_xwalk PRIMARY KEY (source_system_cd, source_patient_id)
);

CREATE TABLE IF NOT EXISTS healthcare_demo_stg.stg_empi_resolved (
    enterprise_patient_id       VARCHAR(64)     NOT NULL,
    primary_source_system_cd    VARCHAR(32)     NOT NULL,
    primary_source_patient_id   VARCHAR(64)     NOT NULL,
    first_name                  VARCHAR(64)     NOT NULL,
    last_name                   VARCHAR(64)     NOT NULL,
    birth_date                  DATE            NOT NULL,
    sex_cd                      CHAR(1)         NOT NULL,
    zip5                        CHAR(5)         NOT NULL,
    phone_last4                 CHAR(4),
    attributed_pcp_nk           VARCHAR(64),
    coverage_segment_cd         VARCHAR(32),
    CONSTRAINT pk_stg_empi_resolved PRIMARY KEY (enterprise_patient_id)
);

CREATE TABLE IF NOT EXISTS healthcare_demo_stg.stg_empi_review_queue (
    candidate_id            BIGSERIAL       PRIMARY KEY,
    src_a_system_cd         VARCHAR(32)     NOT NULL,
    src_a_patient_id        VARCHAR(64)     NOT NULL,
    src_b_system_cd         VARCHAR(32)     NOT NULL,
    src_b_patient_id        VARCHAR(64)     NOT NULL,
    match_score             NUMERIC(5, 3)   NOT NULL,
    status_cd               VARCHAR(16)     NOT NULL DEFAULT 'PENDING',
    created_at              TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- Normalize both sources into a common shape
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW healthcare_demo_stg.v_patient_identity_union AS
SELECT
    'EHR_ENC'                               AS source_system_cd,
    source_patient_id,
    LOWER(TRIM(first_name))                 AS first_name_norm,
    LOWER(TRIM(last_name))                  AS last_name_norm,
    first_name,
    last_name,
    birth_date,
    UPPER(sex_cd)                           AS sex_cd,
    zip5,
    LEFT(zip5, 3)                           AS zip3,
    phone_last4,
    attributed_pcp_nk,
    coverage_segment_cd
FROM healthcare_demo_stg.stg_patient_src_a

UNION ALL

SELECT
    'RCM_CLM'                               AS source_system_cd,
    source_member_id                        AS source_patient_id,
    LOWER(TRIM(given_nm))                   AS first_name_norm,
    LOWER(TRIM(family_nm))                  AS last_name_norm,
    given_nm                                AS first_name,
    family_nm                               AS last_name,
    dob                                     AS birth_date,
    UPPER(gender_cd)                        AS sex_cd,
    postal_cd                               AS zip5,
    LEFT(postal_cd, 3)                       AS zip3,
    phone_last4,
    pcp_id                                  AS attributed_pcp_nk,
    plan_segment                            AS coverage_segment_cd
FROM healthcare_demo_stg.stg_patient_src_b;

-- ---------------------------------------------------------------------------
-- Deterministic candidate pairs (A × B) — R1 / R2
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW healthcare_demo_stg.v_empi_deterministic_pairs AS
SELECT
    a.source_system_cd                      AS src_a_system_cd,
    a.source_patient_id                     AS src_a_patient_id,
    b.source_system_cd                      AS src_b_system_cd,
    b.source_patient_id                     AS src_b_patient_id,
    CASE
        WHEN a.phone_last4 IS NOT NULL
         AND a.phone_last4 = b.phone_last4
            THEN 'R1'
        ELSE 'R2'
    END                                     AS match_rule_cd,
    CASE
        WHEN a.phone_last4 IS NOT NULL
         AND a.phone_last4 = b.phone_last4
            THEN 1.000
        ELSE 0.950
    END                                     AS match_score
FROM healthcare_demo_stg.v_patient_identity_union a
JOIN healthcare_demo_stg.v_patient_identity_union b
  ON a.source_system_cd = 'EHR_ENC'
 AND b.source_system_cd = 'RCM_CLM'
 AND a.birth_date       = b.birth_date
 AND a.last_name_norm   = b.last_name_norm
 AND a.first_name_norm  = b.first_name_norm
 AND a.zip3             = b.zip3;

-- ---------------------------------------------------------------------------
-- Simplified probabilistic residual scoring
-- (pairs that share DOB + last-name prefix but failed deterministic rules)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW healthcare_demo_stg.v_empi_probabilistic_pairs AS
SELECT
    a.source_system_cd                      AS src_a_system_cd,
    a.source_patient_id                     AS src_a_patient_id,
    b.source_system_cd                      AS src_b_system_cd,
    b.source_patient_id                     AS src_b_patient_id,
    (
          CASE WHEN a.birth_date = b.birth_date THEN 0.35 ELSE 0 END
        + CASE WHEN a.last_name_norm = b.last_name_norm THEN 0.25
               WHEN LEFT(a.last_name_norm, 3) = LEFT(b.last_name_norm, 3) THEN 0.12
               ELSE 0 END
        + CASE WHEN a.first_name_norm = b.first_name_norm THEN 0.15
               WHEN LEFT(a.first_name_norm, 1) = LEFT(b.first_name_norm, 1) THEN 0.05
               ELSE 0 END
        + CASE WHEN a.zip3 = b.zip3 THEN 0.15 ELSE 0 END
        + CASE WHEN a.phone_last4 IS NOT NULL
                AND a.phone_last4 = b.phone_last4 THEN 0.10 ELSE 0 END
    )::NUMERIC(5, 3)                        AS match_score
FROM healthcare_demo_stg.v_patient_identity_union a
JOIN healthcare_demo_stg.v_patient_identity_union b
  ON a.source_system_cd = 'EHR_ENC'
 AND b.source_system_cd = 'RCM_CLM'
 AND a.birth_date = b.birth_date
WHERE NOT EXISTS (
    SELECT 1
    FROM healthcare_demo_stg.v_empi_deterministic_pairs d
    WHERE d.src_a_patient_id = a.source_patient_id
      AND d.src_b_patient_id = b.source_patient_id
);

-- ---------------------------------------------------------------------------
-- Apply links: assign enterprise ids
-- ---------------------------------------------------------------------------

-- 1) Clear demo outputs (safe for synthetic reloads)
TRUNCATE healthcare_demo_stg.stg_empi_crosswalk;
TRUNCATE healthcare_demo_stg.stg_empi_resolved;
TRUNCATE healthcare_demo_stg.stg_empi_review_queue;

-- 2) Auto-link deterministic pairs → shared enterprise id
WITH det AS (
    SELECT * FROM healthcare_demo_stg.v_empi_deterministic_pairs
),
assigned AS (
    SELECT
        src_a_system_cd,
        src_a_patient_id,
        src_b_system_cd,
        src_b_patient_id,
        match_rule_cd,
        match_score,
        'EMPI-SYN-' || LPAD(
            ROW_NUMBER() OVER (ORDER BY src_a_patient_id)::TEXT,
            6,
            '0'
        ) AS enterprise_patient_id
    FROM det
)
INSERT INTO healthcare_demo_stg.stg_empi_crosswalk (
    source_system_cd, source_patient_id, enterprise_patient_id, match_rule_cd, match_score
)
SELECT src_a_system_cd, src_a_patient_id, enterprise_patient_id, match_rule_cd, match_score
FROM assigned
UNION ALL
SELECT src_b_system_cd, src_b_patient_id, enterprise_patient_id, match_rule_cd, match_score
FROM assigned;

-- 3) High-confidence probabilistic (≥ 0.92) → auto-link
WITH prob AS (
    SELECT *
    FROM healthcare_demo_stg.v_empi_probabilistic_pairs
    WHERE match_score >= 0.920
      AND src_a_patient_id NOT IN (SELECT source_patient_id FROM healthcare_demo_stg.stg_empi_crosswalk)
      AND src_b_patient_id NOT IN (SELECT source_patient_id FROM healthcare_demo_stg.stg_empi_crosswalk)
),
assigned AS (
    SELECT
        *,
        'EMPI-SYN-' || LPAD(
            (1000 + ROW_NUMBER() OVER (ORDER BY src_a_patient_id))::TEXT,
            6,
            '0'
        ) AS enterprise_patient_id
    FROM prob
)
INSERT INTO healthcare_demo_stg.stg_empi_crosswalk (
    source_system_cd, source_patient_id, enterprise_patient_id, match_rule_cd, match_score
)
SELECT src_a_system_cd, src_a_patient_id, enterprise_patient_id, 'PROB', match_score
FROM assigned
UNION ALL
SELECT src_b_system_cd, src_b_patient_id, enterprise_patient_id, 'PROB', match_score
FROM assigned;

-- 4) Ambiguous band → review queue
INSERT INTO healthcare_demo_stg.stg_empi_review_queue (
    src_a_system_cd, src_a_patient_id, src_b_system_cd, src_b_patient_id, match_score
)
SELECT
    src_a_system_cd,
    src_a_patient_id,
    src_b_system_cd,
    src_b_patient_id,
    match_score
FROM healthcare_demo_stg.v_empi_probabilistic_pairs
WHERE match_score >= 0.750
  AND match_score < 0.920;

-- 5) Unmatched records → new enterprise ids
WITH unmatched AS (
    SELECT *
    FROM healthcare_demo_stg.v_patient_identity_union u
    WHERE NOT EXISTS (
        SELECT 1
        FROM healthcare_demo_stg.stg_empi_crosswalk x
        WHERE x.source_system_cd = u.source_system_cd
          AND x.source_patient_id = u.source_patient_id
    )
)
INSERT INTO healthcare_demo_stg.stg_empi_crosswalk (
    source_system_cd, source_patient_id, enterprise_patient_id, match_rule_cd, match_score
)
SELECT
    source_system_cd,
    source_patient_id,
    'EMPI-SYN-' || LPAD(
        (5000 + ROW_NUMBER() OVER (ORDER BY source_system_cd, source_patient_id))::TEXT,
        6,
        '0'
    ),
    'NEW',
    NULL
FROM unmatched;

-- 6) Build resolved gold demographics (prefer EHR_ENC when present)
INSERT INTO healthcare_demo_stg.stg_empi_resolved (
    enterprise_patient_id,
    primary_source_system_cd,
    primary_source_patient_id,
    first_name,
    last_name,
    birth_date,
    sex_cd,
    zip5,
    phone_last4,
    attributed_pcp_nk,
    coverage_segment_cd
)
SELECT DISTINCT ON (x.enterprise_patient_id)
    x.enterprise_patient_id,
    u.source_system_cd,
    u.source_patient_id,
    u.first_name,
    u.last_name,
    u.birth_date,
    u.sex_cd,
    u.zip5,
    u.phone_last4,
    u.attributed_pcp_nk,
    u.coverage_segment_cd
FROM healthcare_demo_stg.stg_empi_crosswalk x
JOIN healthcare_demo_stg.v_patient_identity_union u
  ON u.source_system_cd = x.source_system_cd
 AND u.source_patient_id = x.source_patient_id
ORDER BY
    x.enterprise_patient_id,
    CASE WHEN u.source_system_cd = 'EHR_ENC' THEN 0 ELSE 1 END,
    u.source_patient_id;
