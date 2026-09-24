-- Every order line must resolve to a customer dimension key.
select
    order_line_nk,
    customer_sk
from {{ ref('fct_orders') }}
where customer_sk is null
