-- =============================================================================
-- Load SYNTHETIC seed CSVs into staging (PostgreSQL \copy example)
-- Run from repo root after creating ddl/00_staging.sql
-- NO REAL PHI — these paths point at fabricated demo files only.
-- =============================================================================

-- Example using psql meta-commands (adjust path as needed):
-- \copy healthcare_demo_stg.stg_patient_src_a FROM 'seeds/synthetic_patients_src_a.csv' CSV HEADER
-- \copy healthcare_demo_stg.stg_patient_src_b FROM 'seeds/synthetic_patients_src_b.csv' CSV HEADER
-- \copy healthcare_demo_stg.stg_provider       FROM 'seeds/synthetic_providers.csv' CSV HEADER
-- \copy healthcare_demo_stg.stg_facility       FROM 'seeds/synthetic_facilities.csv' CSV HEADER
-- \copy healthcare_demo_stg.stg_diagnosis      FROM 'seeds/synthetic_diagnoses.csv' CSV HEADER
-- \copy healthcare_demo_stg.stg_encounters     FROM 'seeds/synthetic_encounters.csv' CSV HEADER
-- \copy healthcare_demo_stg.stg_claims         FROM 'seeds/synthetic_claims.csv' CSV HEADER

-- ANSI-friendly INSERT samples for environments without \copy:

TRUNCATE healthcare_demo_stg.stg_provider;
INSERT INTO healthcare_demo_stg.stg_provider VALUES
('SYN-PRV-1001','1000000001','Dr. Priya Sharma','PC','Primary Care','MD',TRUE,DATE '2020-01-01'),
('SYN-PRV-1002','1000000002','Dr. Marcus Lee','IM','Internal Medicine','MD',TRUE,DATE '2019-06-15'),
('SYN-PRV-1003','1000000003','Dr. Elena Vasquez','PEDS','Pediatrics','MD',TRUE,DATE '2021-03-01'),
('SYN-PRV-1004','1000000004','NP Jordan Blake','PC','Primary Care','NP',TRUE,DATE '2022-08-01'),
('SYN-PRV-1005','1000000005','Dr. Wei Zhang','CARD','Cardiology','MD',TRUE,DATE '2018-11-20'),
('SYN-PRV-1006','1000000006','Dr. Amira Haddad','EM','Emergency Medicine','DO',TRUE,DATE '2020-05-10'),
('SYN-PRV-1007','1000000007','PA Chris Ortega','ORTHO','Orthopedics','PA',TRUE,DATE '2023-01-09');

-- Remaining seed loads: prefer CSV HEADER copy from seeds/*.csv (see README).
-- After staging loads, run:
--   1) entity-resolution/match_patients.sql
--   2) sql/etl/01..05 in order
--   3) data-quality/*.sql
