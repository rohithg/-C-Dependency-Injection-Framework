-- Canonical OTIF definitions (business glossary as SQL)
-- On-time: actual_delivery_date <= planned_delivery_date
-- In-full: shipped_qty >= ordered_qty
-- OTIF: on-time AND in-full
create or replace view analytics.v_otif_definition_check as
select
  s.shipment_id,
  (s.actual_delivery_date is not null
   and s.actual_delivery_date <= s.planned_delivery_date) as is_on_time,
  (s.shipped_qty >= s.ordered_qty) as is_in_full,
  (
    s.actual_delivery_date is not null
    and s.actual_delivery_date <= s.planned_delivery_date
    and s.shipped_qty >= s.ordered_qty
  ) as is_otif
from logistics.shipments s;
