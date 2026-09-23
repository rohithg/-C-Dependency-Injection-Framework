{{
  config(
    materialized='table',
    tags=['marts', 'product']
  )
}}

with events as (

    select * from {{ ref('stg_usage_events') }}

),

accounts as (

    select
        account_id,
        account_created_at,
        is_internal,
        segment,
        region
    from {{ ref('stg_accounts') }}

),

final as (

    select
        {{ dbt_utils.generate_surrogate_key(['e.event_id']) }} as usage_event_sk,
        e.event_id,
        e.account_id,
        a.segment,
        a.region,
        a.is_internal,
        e.event_name,
        e.event_at,
        e.user_id,
        e.properties_json,
        cast(date_trunc('day', e.event_at) as date) as event_date,
        cast(date_trunc('month', e.event_at) as date) as event_month,
        {{ fiscal_year('e.event_at') }} as event_fiscal_year,
        {{ dbt.datediff('a.account_created_at', 'e.event_at', 'day') }} as days_since_account_created,
        {{ dbt.current_timestamp() }} as dbt_updated_at

    from events e
    inner join accounts a
        on e.account_id = a.account_id

)

select * from final
