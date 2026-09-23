{{
  config(
    materialized='view',
    tags=['staging', 'synthetic']
  )
}}

-- SYNTHETIC DEMO ONLY — NO REAL PHI

select
    source_member_id                                as source_patient_id,
    lower(trim(given_nm))                           as first_name_norm,
    lower(trim(family_nm))                          as last_name_norm,
    given_nm                                        as first_name,
    family_nm                                       as last_name,
    dob                                             as birth_date,
    upper(gender_cd)                                as sex_cd,
    postal_cd                                       as zip5,
    left(postal_cd, 3)                               as zip3,
    phone_last4,
    pcp_id                                          as attributed_pcp_nk,
    plan_segment                                    as coverage_segment_cd,
    extract_ts,
    'RCM_CLM'                                       as source_system_cd
from {{ source('healthcare_raw', 'stg_patient_src_b') }}
