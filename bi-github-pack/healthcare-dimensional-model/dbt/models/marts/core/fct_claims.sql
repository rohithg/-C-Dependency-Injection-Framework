{{
  config(
    materialized='table',
    tags=['marts', 'core', 'fact', 'synthetic']
  )
}}

-- SYNTHETIC DEMO ONLY — NO REAL PHI

with clm as (
    select * from {{ ref('stg_claims') }}
),
xwalk as (
    select * from {{ source('healthcare_raw', 'stg_empi_crosswalk') }}
    where source_system_cd = 'RCM_CLM'
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
    {{ dbt_utils.generate_surrogate_key(['clm.claim_nk']) }} as claim_sk_hash,
    clm.claim_nk,
    patients.enterprise_patient_id,
    patients.patient_sk_hash                            as patient_sk_hash,
    providers.provider_sk_hash                          as billing_provider_sk_hash,
    facilities.facility_sk_hash,
    diagnoses.diagnosis_sk_hash                         as primary_dx_sk_hash,
    clm.primary_icd10_cd,
    clm.service_date,
    clm.paid_date,
    clm.claim_type_cd,
    clm.claim_status,
    clm.place_of_service_cd,
    clm.billed_amt,
    clm.allowed_amt,
    clm.paid_amt,
    clm.member_responsibility,
    'RCM_CLM'                                           as source_system_cd
from clm
inner join xwalk
    on xwalk.source_patient_id = clm.source_patient_id
inner join patients
    on patients.enterprise_patient_id = xwalk.enterprise_patient_id
inner join providers
    on providers.provider_nk = clm.billing_provider_nk
left join facilities
    on facilities.facility_nk = clm.facility_nk
inner join diagnoses
    on diagnoses.icd10_cd = clm.primary_icd10_cd
