-- Recognized invoice totals should be non-negative for OPEN/PAID/PARTIAL invoices.
select
    invoice_nk,
    invoice_status,
    total_amount
from {{ ref('fct_finance') }}
where invoice_status in ('OPEN', 'PAID', 'PARTIAL', 'OVERDUE')
  and total_amount < 0
