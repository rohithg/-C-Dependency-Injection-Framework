{{
  config(
    materialized='table',
    tags=['marts', 'core', 'dimension', 'synthetic']
  )
}}

select
    {{ dbt_utils.generate_surrogate_key(['facility_nk']) }} as facility_sk_hash,
    facility_nk,
    facility_name,
    facility_type,
    region_cd,
    state_cd,
    zip3,
    is_active
from {{ source('healthcare_raw', 'stg_facility') }}
