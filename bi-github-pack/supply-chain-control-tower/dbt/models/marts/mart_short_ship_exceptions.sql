select
  shipment_id,
  order_id,
  region,
  bu,
  carrier,
  ordered_qty,
  shipped_qty,
  ordered_qty - shipped_qty as short_qty,
  freight_cost,
  is_on_time,
  is_otif
from {{ ref('int_shipment_otif') }}
where shipped_qty < ordered_qty
