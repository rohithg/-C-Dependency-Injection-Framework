{{
  config(
    materialized='table',
    tags=['marts', 'dimension']
  )
}}

with locations as (
    select * from {{ ref('stg_locations') }}
)

select
    {{ generate_surrogate_key(['location_id']) }} as location_sk,
    location_id as location_nk,
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
    created_at as location_created_at,
    updated_at as location_updated_at,
    current_timestamp as dbt_updated_at
from locations
