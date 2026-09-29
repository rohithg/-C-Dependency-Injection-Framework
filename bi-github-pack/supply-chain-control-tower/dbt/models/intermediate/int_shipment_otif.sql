with s as (select * from {{ ref('stg_shipments') }}),
o as (select * from {{ ref('stg_orders') }})
select
  s.*, o.customer_id, o.order_value, o.priority,
  case when s.actual_delivery_date is not null
        and s.actual_delivery_date <= s.planned_delivery_date
       then true else false end as is_on_time,
  case when s.shipped_qty >= s.ordered_qty then true else false end as is_in_full,
  case when s.actual_delivery_date is not null
        and s.actual_delivery_date <= s.planned_delivery_date
        and s.shipped_qty >= s.ordered_qty
       then true else false end as is_otif
from s left join o on s.order_id = o.order_id
