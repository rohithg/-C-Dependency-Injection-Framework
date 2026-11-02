{{
  config(
    materialized='view',
    tags=['staging', 'synthetic']
  )
}}

-- SYNTHETIC DEMO ONLY — NO REAL PHI
-- Light rename / type-cast layer over EHR patient staging.

select
    source_patient_id,
    lower(trim(first_name))                         as first_name_norm,
    lower(trim(last_name))                          as last_name_norm,
    first_name,
    last_name,
    birth_date,
    upper(sex_cd)                                   as sex_cd,
    zip5,
    left(zip5, 3)                                   as zip3,
    phone_last4,
    attributed_pcp_nk,
    coverage_segment_cd,
    extract_ts,
    'EHR_ENC'                                       as source_system_cd
from {{ source('healthcare_raw', 'stg_patient_src_a') }}
