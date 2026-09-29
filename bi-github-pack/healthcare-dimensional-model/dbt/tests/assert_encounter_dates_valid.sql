-- Singular test: encounter discharge date must not precede encounter date
-- Returns failing rows (dbt expects 0 rows)

select
    encounter_nk,
    encounter_date,
    discharge_date
from {{ ref('fct_encounters') }}
where discharge_date is not null
  and discharge_date < encounter_date
