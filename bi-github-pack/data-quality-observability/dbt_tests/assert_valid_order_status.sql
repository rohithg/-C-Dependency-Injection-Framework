select order_id, status
from {{ ref('stg_orders') }}
where status not in ('OPEN', 'CLOSED', 'CANCELLED', 'PARTIAL')
