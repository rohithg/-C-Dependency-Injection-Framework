select
  order_id, customer_id,
  cast(order_date as date) as order_date,
  cast(order_value as double) as order_value,
  priority
from {{ ref('raw_orders') }}
