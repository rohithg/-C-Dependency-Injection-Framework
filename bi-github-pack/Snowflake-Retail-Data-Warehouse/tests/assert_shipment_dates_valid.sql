-- Shipments cannot deliver before they ship; delivered rows need a ship date.
select
    shipment_nk,
    actual_ship_date,
    actual_delivery_date,
    shipment_status
from {{ ref('fct_shipments') }}
where
    (
        actual_delivery_date is not null
        and actual_ship_date is not null
        and actual_delivery_date < actual_ship_date
    )
    or (
        shipment_status in ('DELIVERED', 'CLOSED')
        and actual_ship_date is null
    )
