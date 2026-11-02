{{
  config(
    materialized='view',
    tags=['intermediate', 'logistics']
  )
}}

with shipments as (
    select * from {{ ref('stg_shipments') }}
),

orders as (
    select distinct
        order_id,
        customer_id,
        order_date,
        order_status
    from {{ ref('stg_orders') }}
),

origin as (
    select
        location_id,
        location_name as origin_name,
        city as origin_city,
        state_province as origin_state,
        region as origin_region
    from {{ ref('stg_locations') }}
),

destination as (
    select
        location_id,
        location_name as destination_name,
        city as destination_city,
        state_province as destination_state,
        region as destination_region
    from {{ ref('stg_locations') }}
),

joined as (
    select
        s.shipment_id,
        s.shipment_number,
        s.order_id,
        o.customer_id,
        o.order_date,
        o.order_status,
        s.carrier_code,
        s.carrier_name,
        s.transportation_mode,
        s.shipment_status,
        s.origin_location_id,
        orig.origin_name,
        orig.origin_city,
        orig.origin_state,
        orig.origin_region,
        s.destination_location_id,
        dest.destination_name,
        dest.destination_city,
        dest.destination_state,
        dest.destination_region,
        s.planned_ship_date,
        s.actual_ship_date,
        s.planned_delivery_date,
        s.actual_delivery_date,
        s.freight_cost,
        s.weight_lbs,
        s.pallet_count,
        s.tracking_number,
        s.yard_checkin_at,
        s.yard_checkout_at,
        s.is_on_time,
        s.delivery_variance_days,
        case
            when s.yard_checkin_at is not null and s.yard_checkout_at is not null
            then (
                extract(epoch from s.yard_checkout_at)
                - extract(epoch from s.yard_checkin_at)
            ) / 3600.0
            else null
        end as yard_dwell_hours,
        s.created_at,
        s.updated_at
    from shipments s
    left join orders o on s.order_id = o.order_id
    left join origin orig on s.origin_location_id = orig.location_id
    left join destination dest on s.destination_location_id = dest.location_id
)

select * from joined
