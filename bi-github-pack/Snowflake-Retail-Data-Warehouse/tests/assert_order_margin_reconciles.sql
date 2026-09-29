-- Order line gross margin must equal net amount − COGS (within 0.01 for rounding).
select
    order_line_nk,
    line_net_amount,
    line_cogs,
    line_gross_margin,
    abs(line_gross_margin - (line_net_amount - line_cogs)) as margin_delta
from {{ ref('fct_orders') }}
where abs(line_gross_margin - (line_net_amount - line_cogs)) > 0.01
