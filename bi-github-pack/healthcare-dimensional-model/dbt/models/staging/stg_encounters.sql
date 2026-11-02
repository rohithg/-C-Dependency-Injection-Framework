{{
  config(
    materialized='view',
    tags=['staging', 'synthetic']
  )
}}

-- SYNTHETIC DEMO ONLY — NO REAL PHI

select
    encounter_nk,
    source_patient_id,
    provider_nk,
    facility_nk,
    upper(trim(primary_icd10_cd))                   as primary_icd10_cd,
    encounter_date,
    discharge_date,
    encounter_type,
    admission_type_cd,
    discharge_disposition,
    length_of_stay_days,
    total_charges_amt,
    is_readmit_30d
from {{ source('healthcare_raw', 'stg_encounters') }}
