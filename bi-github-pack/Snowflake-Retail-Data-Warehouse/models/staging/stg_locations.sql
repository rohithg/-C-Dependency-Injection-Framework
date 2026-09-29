{{
  config(
    materialized='view',
    tags=['staging', 'yms', 'logistics']
  )
}}

with source as (
    select * from {{ source('raw_logistics', 'raw_locations') }}
),

renamed as (
    select
        cast(location_id as varchar) as location_id,
        cast(location_code as varchar) as location_code,
        trim(cast(location_name as varchar)) as location_name,
        upper(trim(cast(location_type as varchar))) as location_type,
        trim(cast(address_line1 as varchar)) as address_line1,
        trim(cast(city as varchar)) as city,
        trim(cast(state_province as varchar)) as state_province,
        trim(cast(postal_code as varchar)) as postal_code,
        trim(cast(country as varchar)) as country,
        cast(region as varchar) as region,
        cast(time_zone as varchar) as time_zone,
        case
            when lower(cast(is_active as varchar)) in ('true', '1', 't', 'yes') then true
            else false
        end as is_active,
        cast(nullif(trim(cast(square_footage as varchar)), '') as integer) as square_footage,
        cast(nullif(trim(cast(dock_door_count as varchar)), '') as integer) as dock_door_count,
        cast(created_at as timestamp) as created_at,
        cast(updated_at as timestamp) as updated_at,
        cast(_loaded_at as timestamp) as _loaded_at,
        cast(_source_system as varchar) as _source_system
    from source
),

deduped as (
    select
        *,
        row_number() over (
            partition by location_id
            order by updated_at desc, _loaded_at desc
        ) as _row_num
    from renamed
)

select
    location_id,
    location_code,
    location_name,
    location_type,
    address_line1,
    city,
    state_province,
    postal_code,
    country,
    region,
    time_zone,
    is_active,
    square_footage,
    dock_door_count,
    created_at,
    updated_at,
    _loaded_at,
    _source_system
from deduped
where _row_num = 1
