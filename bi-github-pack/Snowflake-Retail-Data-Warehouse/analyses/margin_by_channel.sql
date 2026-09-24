-- Gross margin contribution by order channel — Sales vs Finance conversation starter.

select
    order_channel,
    count(distinct order_id) as orders,
    count(*) as order_lines,
    sum(line_net_amount) as net_sales,
    sum(line_cogs) as cogs,
    sum(line_gross_margin) as gross_margin,
    round(
        sum(line_gross_margin) / nullif(sum(line_net_amount), 0),
        4
    ) as gross_margin_pct
from {{ ref('fct_orders') }}
where order_status not in ('CANCELLED', 'DRAFT')
group by 1
order by net_sales desc
