{{
  config(
    materialized='view',
    tags=['staging', 'synthetic']
  )
}}

-- SYNTHETIC DEMO ONLY — NO REAL PHI

select
    claim_nk,
    source_member_id                                as source_patient_id,
    billing_provider_nk,
    facility_nk,
    upper(trim(primary_icd10_cd))                   as primary_icd10_cd,
    service_date,
    paid_date,
    claim_type_cd,
    claim_status,
    place_of_service_cd,
    billed_amt,
    allowed_amt,
    paid_amt,
    member_responsibility
from {{ source('healthcare_raw', 'stg_claims') }}
