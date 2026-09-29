{{
  config(
    materialized='table',
    tags=['marts', 'fact', 'logistics']
  )
}}

with shipments as (
    select * from {{ ref('int_shipments_enriched') }}
),

customers as (
    select customer_sk, customer_nk from {{ ref('dim_customer') }}
),

dates_ship as (
    select date_sk, date_day from {{ ref('dim_date') }}
),

dates_delivery as (
    select date_sk, date_day from {{ ref('dim_date') }}
),

origin as (
    select location_sk, location_nk from {{ ref('dim_location') }}
),

destination as (
    select location_sk, location_nk from {{ ref('dim_location') }}
)

select
    {{ generate_surrogate_key(['s.shipment_id']) }} as shipment_sk,
    s.shipment_id as shipment_nk,
    s.shipment_number,
    s.order_id,
    c.customer_sk,
    ds.date_sk as actual_ship_date_sk,
    dd.date_sk as actual_delivery_date_sk,
    o.location_sk as origin_location_sk,
    dest.location_sk as destination_location_sk,
    s.carrier_code,
    s.carrier_name,
    s.transportation_mode,
    s.shipment_status,
    s.planned_ship_date,
    s.actual_ship_date,
    s.planned_delivery_date,
    s.actual_delivery_date,
    s.freight_cost,
    s.weight_lbs,
    s.pallet_count,
    s.tracking_number,
    s.is_on_time,
    s.delivery_variance_days,
    s.yard_dwell_hours,
    s.yard_checkin_at,
    s.yard_checkout_at,
    s.origin_city,
    s.origin_state,
    s.origin_region,
    s.destination_city,
    s.destination_state,
    s.destination_region,
    s.created_at,
    s.updated_at,
    current_timestamp as dbt_updated_at
from shipments s
left join customers c on s.customer_id = c.customer_nk
left join dates_ship ds on s.actual_ship_date = ds.date_day
left join dates_delivery dd on s.actual_delivery_date = dd.date_day
left join origin o on s.origin_location_id = o.location_nk
left join destination dest on s.destination_location_id = dest.location_nk
