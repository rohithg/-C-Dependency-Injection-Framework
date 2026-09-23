{{
  config(
    materialized='view',
    tags=['staging']
  )
}}

with source as (

    select * from {{ ref('seed_subscriptions') }}

),

renamed as (

    select
        subscription_id,
        account_id,
        plan_id,
        lower(trim(status)) as status,
        cast(mrr_cents as {{ dbt.type_int() }}) as mrr_cents,
        {{ cents_to_dollars('mrr_cents') }} as mrr_usd,
        cast(started_at as {{ dbt.type_timestamp() }}) as subscription_started_at,
        cast(ended_at as {{ dbt.type_timestamp() }}) as subscription_ended_at,
        nullif(trim(churn_reason), '') as churn_reason,
        case
            when lower(trim(status)) = 'active' then true
            else false
        end as is_currently_active,
        {{ dbt.current_timestamp() }} as _loaded_at

    from source

)

select * from renamed
