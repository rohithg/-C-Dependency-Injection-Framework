{{
  config(
    materialized='table',
    tags=['metrics', 'product']
  )
}}

/*
  Activation Rate — metrics-as-code definition
*/

with accounts as (

    select
        account_id,
        account_created_at,
        is_activated,
        is_internal
    from {{ ref('dim_accounts') }}
    where not is_internal

),

overall as (

    select
        cast({{ dbt.current_timestamp() }} as date) as as_of_date,
        cast(null as date) as cohort_month,
        'overall' as grain,
        count(*) as accounts_started,
        sum(case when is_activated then 1 else 0 end) as accounts_activated,
        {{ safe_divide(
            'sum(case when is_activated then 1 else 0 end)',
            'count(*)'
        ) }} as activation_rate,
        {{ var('activation_event_threshold', 3) }} as activation_event_threshold,
        {{ var('activation_window_days', 14) }} as activation_window_days,
        'activation_rate' as metric_name,
        'Activated accounts / started accounts (non-internal)' as metric_definition,
        {{ dbt.current_timestamp() }} as calculated_at

    from accounts

),

by_cohort as (

    select
        cast({{ dbt.current_timestamp() }} as date) as as_of_date,
        cast(date_trunc('month', account_created_at) as date) as cohort_month,
        'signup_month' as grain,
        count(*) as accounts_started,
        sum(case when is_activated then 1 else 0 end) as accounts_activated,
        {{ safe_divide(
            'sum(case when is_activated then 1 else 0 end)',
            'count(*)'
        ) }} as activation_rate,
        {{ var('activation_event_threshold', 3) }} as activation_event_threshold,
        {{ var('activation_window_days', 14) }} as activation_window_days,
        'activation_rate' as metric_name,
        'Activated accounts / started accounts (non-internal)' as metric_definition,
        {{ dbt.current_timestamp() }} as calculated_at

    from accounts
    group by 1, 2, 3

)

select * from overall
union all
select * from by_cohort
