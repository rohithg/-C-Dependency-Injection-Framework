{{
  config(
    materialized='table',
    tags=['marts', 'core', 'dimension', 'synthetic']
  )
}}

-- SYNTHETIC DEMO — illustrates SCD2 current slice for BI consumption.
-- Full SCD2 history load lives in sql/etl/02_load_dim_patient_scd2.sql.

with resolved as (
    select * from {{ source('healthcare_raw', 'stg_empi_resolved') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['enterprise_patient_id', 'coverage_segment_cd', 'zip5']) }}
                                                        as patient_sk_hash,
    enterprise_patient_id,
    primary_source_patient_id                           as patient_nk,
    primary_source_system_cd                            as source_system_cd,
    -- Demo tokenization (warehouse-native hashing preferred in production)
    md5(lower(trim(first_name)))                        as first_name_token,
    md5(lower(trim(last_name)))                         as last_name_token,
    birth_date,
    sex_cd,
    left(zip5, 3)                                       as zip3,
    attributed_pcp_nk,
    coverage_segment_cd,
    current_date                                        as effective_start_dt,
    cast(null as date)                                  as effective_end_dt,
    true                                                as is_current
from resolved
