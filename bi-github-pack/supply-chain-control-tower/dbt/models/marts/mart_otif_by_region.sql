select
  region,
  sum(shipments) as shipments,
  sum(on_time_rate * shipments) / nullif(sum(shipments), 0) as on_time_rate,
  sum(in_full_rate * shipments) / nullif(sum(shipments), 0) as in_full_rate,
  sum(otif_rate * shipments) / nullif(sum(shipments), 0) as otif_rate,
  sum(total_freight_cost) as total_freight_cost,
  sum(avg_yard_dwell_hours * shipments) / nullif(sum(shipments), 0) as avg_yard_dwell_hours
from {{ ref('mart_otif_daily') }}
group by 1
