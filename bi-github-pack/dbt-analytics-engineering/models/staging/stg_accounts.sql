{{
  config(
    materialized='view',
    tags=['staging']
  )
}}

with source as (

    select * from {{ ref('seed_accounts') }}

),

renamed as (

    select
        account_id,
        trim(account_name) as account_name,
        lower(trim(industry)) as industry,
        lower(trim(segment)) as segment,
        upper(trim(region)) as region,
        cast(created_at as {{ dbt.type_timestamp() }}) as account_created_at,
        cast(is_internal as boolean) as is_internal,
        {{ dbt.current_timestamp() }} as _loaded_at

    from source

)

select * from renamed
