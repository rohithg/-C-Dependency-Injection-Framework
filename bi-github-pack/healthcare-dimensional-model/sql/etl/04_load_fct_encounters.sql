-- =============================================================================
-- 04_load_fct_encounters.sql — encounter fact load with SK lookups
-- SYNTHETIC DEMO ONLY — NO REAL PHI
-- =============================================================================

CREATE SEQUENCE IF NOT EXISTS healthcare_demo.seq_encounter_sk START 50000;

INSERT INTO healthcare_demo.fct_encounters (
    encounter_sk,
    encounter_nk,
    patient_sk,
    provider_sk,
    facility_sk,
    primary_dx_sk,
    encounter_date_sk,
    discharge_date_sk,
    encounter_type,
    admission_type_cd,
    discharge_disposition,
    length_of_stay_days,
    total_charges_amt,
    is_readmit_30d,
    source_system_cd,
    loaded_at
)
SELECT
    NEXTVAL('healthcare_demo.seq_encounter_sk'),
    e.encounter_nk,
    p.patient_sk,
    pr.provider_sk,
    f.facility_sk,
    d.diagnosis_sk,
    dd.date_sk                                                          AS encounter_date_sk,
    dd_out.date_sk                                                      AS discharge_date_sk,
    e.encounter_type,
    e.admission_type_cd,
    e.discharge_disposition,
    e.length_of_stay_days,
    e.total_charges_amt,
    e.is_readmit_30d,
    'EHR_ENC',
    CURRENT_TIMESTAMP
FROM healthcare_demo_stg.stg_encounters e
-- Map source patient id → enterprise id → current patient_sk
JOIN healthcare_demo_stg.stg_empi_crosswalk x
    ON x.source_system_cd = 'EHR_ENC'
   AND x.source_patient_id = e.source_patient_id
JOIN healthcare_demo.dim_patient p
    ON p.enterprise_patient_id = x.enterprise_patient_id
   AND p.is_current = TRUE
JOIN healthcare_demo.dim_provider pr
    ON pr.provider_nk = e.provider_nk
JOIN healthcare_demo.dim_facility f
    ON f.facility_nk = e.facility_nk
JOIN healthcare_demo.dim_diagnosis d
    ON d.icd10_cd = e.primary_icd10_cd
JOIN healthcare_demo.dim_date dd
    ON dd.full_date = e.encounter_date
LEFT JOIN healthcare_demo.dim_date dd_out
    ON dd_out.full_date = e.discharge_date
ON CONFLICT (encounter_nk) DO UPDATE SET
    patient_sk            = EXCLUDED.patient_sk,
    provider_sk           = EXCLUDED.provider_sk,
    facility_sk           = EXCLUDED.facility_sk,
    primary_dx_sk         = EXCLUDED.primary_dx_sk,
    encounter_date_sk     = EXCLUDED.encounter_date_sk,
    discharge_date_sk     = EXCLUDED.discharge_date_sk,
    encounter_type        = EXCLUDED.encounter_type,
    admission_type_cd     = EXCLUDED.admission_type_cd,
    discharge_disposition = EXCLUDED.discharge_disposition,
    length_of_stay_days   = EXCLUDED.length_of_stay_days,
    total_charges_amt     = EXCLUDED.total_charges_amt,
    is_readmit_30d        = EXCLUDED.is_readmit_30d,
    loaded_at             = CURRENT_TIMESTAMP;
