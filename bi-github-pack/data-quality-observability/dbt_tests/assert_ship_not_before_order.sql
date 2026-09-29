select order_id, order_date, ship_date
from {{ ref('stg_orders') }}
where ship_date is not null and order_date is not null and ship_date < order_date
