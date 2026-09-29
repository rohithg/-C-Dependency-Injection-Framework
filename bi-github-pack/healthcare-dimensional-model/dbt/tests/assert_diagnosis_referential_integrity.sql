-- Singular test: ICD-10 codes on facts must exist in dim_diagnosis

select
    'encounter' as fact_type,
    e.encounter_nk as record_nk,
    e.primary_icd10_cd
from {{ ref('fct_encounters') }} e
left join {{ ref('dim_diagnosis') }} d
    on d.icd10_cd = e.primary_icd10_cd
where d.icd10_cd is null

union all

select
    'claim' as fact_type,
    c.claim_nk as record_nk,
    c.primary_icd10_cd
from {{ ref('fct_claims') }} c
left join {{ ref('dim_diagnosis') }} d
    on d.icd10_cd = c.primary_icd10_cd
where d.icd10_cd is null
