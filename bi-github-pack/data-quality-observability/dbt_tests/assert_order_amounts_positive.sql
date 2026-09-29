select order_id, amount
from {{ ref('stg_orders') }}
where amount is null or amount <= 0
