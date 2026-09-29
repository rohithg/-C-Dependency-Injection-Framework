select
  coalesce(actual_delivery_date, planned_delivery_date) as metric_date,
  region, bu, carrier,
  count(*) as shipments,
  avg(case when is_on_time then 1.0 else 0.0 end) as on_time_rate,
  avg(case when is_in_full then 1.0 else 0.0 end) as in_full_rate,
  avg(case when is_otif then 1.0 else 0.0 end) as otif_rate,
  avg(yard_dwell_hours) as avg_yard_dwell_hours,
  avg(freight_cost) as avg_freight_cost,
  sum(freight_cost) as total_freight_cost
from {{ ref('int_shipment_otif') }}
group by 1,2,3,4
