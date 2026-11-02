{{
  config(
    materialized='table',
    tags=['marts', 'core', 'dimension', 'synthetic']
  )
}}

select
    {{ dbt_utils.generate_surrogate_key(['icd10_cd']) }} as diagnosis_sk_hash,
    icd10_cd,
    icd10_desc,
    chapter_cd,
    chapter_desc,
    clinical_group,
    is_billable
from {{ source('healthcare_raw', 'stg_diagnosis') }}
