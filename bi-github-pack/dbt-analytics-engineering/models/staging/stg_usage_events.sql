{{
  config(
    materialized='view',
    tags=['staging']
  )
}}

with source as (

    select * from {{ ref('seed_usage_events') }}

),

renamed as (

    select
        event_id,
        account_id,
        lower(trim(event_name)) as event_name,
        cast(event_at as {{ dbt.type_timestamp() }}) as event_at,
        user_id,
        properties_json,
        {{ dbt.current_timestamp() }} as _loaded_at

    from source

)

select * from renamed
