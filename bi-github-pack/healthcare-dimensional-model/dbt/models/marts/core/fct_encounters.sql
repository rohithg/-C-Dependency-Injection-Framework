{{
  config(
    materialized='table',
    tags=['marts', 'core', 'fact', 'synthetic']
  )
}}

-- SYNTHETIC DEMO ONLY — NO REAL PHI
-- Joins staging encounters to current patient + conformed dims.

with enc as (
    select * from {{ ref('stg_encounters') }}
),
xwalk as (
    select * from {{ source('healthcare_raw', 'stg_empi_crosswalk') }}
    where source_system_cd = 'EHR_ENC'
),
patients as (
    select * from {{ ref('dim_patient') }}
    where is_current
),
providers as (
    select * from {{ ref('dim_provider') }}
),
facilities as (
    select * from {{ ref('dim_facility') }}
),
diagnoses as (
    select * from {{ ref('dim_diagnosis') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['enc.encounter_nk']) }} as encounter_sk_hash,
    enc.encounter_nk,
    patients.enterprise_patient_id,
    patients.patient_sk_hash                            as patient_sk_hash,
    providers.provider_sk_hash,
    facilities.facility_sk_hash,
    diagnoses.diagnosis_sk_hash                         as primary_dx_sk_hash,
    enc.primary_icd10_cd,
    enc.encounter_date,
    enc.discharge_date,
    enc.encounter_type,
    enc.admission_type_cd,
    enc.discharge_disposition,
    enc.length_of_stay_days,
    enc.total_charges_amt,
    enc.is_readmit_30d,
    'EHR_ENC'                                           as source_system_cd
from enc
inner join xwalk
    on xwalk.source_patient_id = enc.source_patient_id
inner join patients
    on patients.enterprise_patient_id = xwalk.enterprise_patient_id
inner join providers
    on providers.provider_nk = enc.provider_nk
inner join facilities
    on facilities.facility_nk = enc.facility_nk
inner join diagnoses
    on diagnoses.icd10_cd = enc.primary_icd10_cd
