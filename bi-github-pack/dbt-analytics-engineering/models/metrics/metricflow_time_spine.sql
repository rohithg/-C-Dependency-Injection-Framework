{{
  config(
    materialized='table',
    schema='metrics'
  )
}}

/*
  MetricFlow time spine — required when semantic models are defined.
  Daily grain; recursive CTE + dbt.dateadd for cross-warehouse CI.
*/

with recursive date_spine as (

    select cast('2023-01-01' as date) as date_day

    union all

    select cast({{ dbt.dateadd('day', 1, 'date_day') }} as date) as date_day
    from date_spine
    where date_day < cast('2026-12-31' as date)

)

select date_day
from date_spine
