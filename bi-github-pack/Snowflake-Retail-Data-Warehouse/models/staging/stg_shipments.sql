{{
  config(
    materialized='view',
    tags=['staging', 'tms', 'logistics']
  )
}}

with source as (
    select * from {{ source('raw_logistics', 'raw_shipments') }}
),

renamed as (
    select
        cast(shipment_id as varchar) as shipment_id,
        cast(shipment_number as varchar) as shipment_number,
        cast(order_id as varchar) as order_id,
        cast(carrier_code as varchar) as carrier_code,
        trim(carrier_name) as carrier_name,
        trim(mode) as transportation_mode,
        upper(trim(shipment_status)) as shipment_status,
        cast(origin_location_id as varchar) as origin_location_id,
        cast(destination_location_id as varchar) as destination_location_id,
        cast(nullif(trim(cast(planned_ship_date as varchar)), '') as date) as planned_ship_date,
        cast(nullif(trim(cast(actual_ship_date as varchar)), '') as date) as actual_ship_date,
        cast(nullif(trim(cast(planned_delivery_date as varchar)), '') as date) as planned_delivery_date,
        cast(nullif(trim(cast(actual_delivery_date as varchar)), '') as date) as actual_delivery_date,
        cast(freight_cost as decimal(18, 2)) as freight_cost,
        cast(weight_lbs as decimal(12, 4)) as weight_lbs,
        cast(pallet_count as integer) as pallet_count,
        cast(tracking_number as varchar) as tracking_number,
        cast(nullif(trim(cast(yard_checkin_at as varchar)), '') as timestamp) as yard_checkin_at,
        cast(nullif(trim(cast(yard_checkout_at as varchar)), '') as timestamp) as yard_checkout_at,
        cast(created_at as timestamp) as created_at,
        cast(updated_at as timestamp) as updated_at,
        cast(_loaded_at as timestamp) as _loaded_at,
        cast(_source_system as varchar) as _source_system
    from source
),

enriched as (
    select
        *,
        case
            when actual_delivery_date is not null
                and planned_delivery_date is not null
                and actual_delivery_date <= planned_delivery_date
            then 1
            when actual_delivery_date is not null
                and planned_delivery_date is not null
            then 0
            else null
        end as is_on_time,
        case
            when actual_delivery_date is not null and planned_delivery_date is not null
            then cast(actual_delivery_date as date) - cast(planned_delivery_date as date)
            else null
        end as delivery_variance_days,
        row_number() over (
            partition by shipment_id
            order by updated_at desc, _loaded_at desc
        ) as _row_num
    from renamed
)

select
    shipment_id,
    shipment_number,
    order_id,
    carrier_code,
    carrier_name,
    transportation_mode,
    shipment_status,
    origin_location_id,
    destination_location_id,
    planned_ship_date,
    actual_ship_date,
    planned_delivery_date,
    actual_delivery_date,
    freight_cost,
    weight_lbs,
    pallet_count,
    tracking_number,
    yard_checkin_at,
    yard_checkout_at,
    is_on_time,
    delivery_variance_days,
    created_at,
    updated_at,
    _loaded_at,
    _source_system
from enriched
where _row_num = 1
