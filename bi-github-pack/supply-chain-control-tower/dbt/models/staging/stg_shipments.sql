select
  shipment_id, order_id, bu, region, carrier, mode,
  cast(planned_ship_date as date) as planned_ship_date,
  cast(actual_ship_date as date) as actual_ship_date,
  cast(planned_delivery_date as date) as planned_delivery_date,
  cast(nullif(actual_delivery_date, '') as date) as actual_delivery_date,
  cast(ordered_qty as integer) as ordered_qty,
  cast(shipped_qty as integer) as shipped_qty,
  cast(freight_cost as double) as freight_cost,
  cast(yard_dwell_hours as double) as yard_dwell_hours,
  status
from {{ ref('raw_shipments') }}
