{{
  config(
    materialized='table',
    tags=['marts', 'core', 'dimension', 'synthetic']
  )
}}

select
    {{ dbt_utils.generate_surrogate_key(['provider_nk']) }} as provider_sk_hash,
    provider_nk,
    npi_synthetic,
    provider_name,
    specialty_cd,
    specialty_desc,
    provider_type_cd,
    is_active,
    effective_start_dt
from {{ source('healthcare_raw', 'stg_provider') }}
