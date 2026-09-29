{{
  config(
    materialized='view',
    tags=['intermediate', 'product']
  )
}}

{% set activation_threshold = var('activation_event_threshold', 3) %}
{% set activation_window = var('activation_window_days', 14) %}

with accounts as (

    select
        account_id,
        account_created_at,
        is_internal
    from {{ ref('stg_accounts') }}

),

events as (

    select
        account_id,
        event_id,
        event_name,
        event_at
    from {{ ref('stg_usage_events') }}
    where event_name not in ('signup_completed')

),

activation_window_events as (

    select
        a.account_id,
        a.account_created_at,
        a.is_internal,
        count(distinct e.event_id) as qualifying_event_count,
        count(distinct e.event_name) as distinct_event_types,
        min(e.event_at) as first_product_event_at,
        max(e.event_at) as last_product_event_in_window_at

    from accounts a
    left join events e
        on a.account_id = e.account_id
        and e.event_at >= a.account_created_at
        and e.event_at < {{ dbt.dateadd('day', activation_window, 'a.account_created_at') }}

    group by 1, 2, 3

),

final as (

    select
        account_id,
        account_created_at,
        is_internal,
        qualifying_event_count,
        distinct_event_types,
        first_product_event_at,
        last_product_event_in_window_at,
        case
            when qualifying_event_count >= {{ activation_threshold }} then true
            else false
        end as is_activated,
        {{ activation_window }} as activation_window_days,
        {{ activation_threshold }} as activation_event_threshold

    from activation_window_events

)

select * from final
