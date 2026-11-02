{{
  config(
    materialized='view',
    tags=['intermediate', 'finance']
  )
}}

with invoices as (
    select * from {{ ref('stg_invoices') }}
),

order_totals as (
    select
        order_id,
        customer_id,
        sum(line_net_amount) as order_net_amount,
        sum(line_gross_amount) as order_gross_amount,
        sum(line_cogs) as order_cogs,
        sum(line_gross_margin) as order_gross_margin,
        count(distinct order_line_id) as order_line_count
    from {{ ref('int_order_lines_enriched') }}
    group by 1, 2
),

joined as (
    select
        i.invoice_id,
        i.invoice_number,
        i.order_id,
        i.customer_id,
        i.invoice_date,
        i.due_date,
        i.paid_date,
        i.invoice_status,
        i.subtotal_amount,
        i.tax_amount,
        i.freight_amount,
        i.total_amount,
        i.amount_paid,
        i.balance_due,
        i.is_overdue,
        i.days_to_pay,
        i.currency_code,
        i.payment_terms_days,
        ot.order_net_amount,
        ot.order_gross_amount,
        ot.order_cogs,
        ot.order_gross_margin,
        ot.order_line_count,
        {{ safe_divide('i.amount_paid', 'nullif(i.total_amount, 0)') }} as collection_rate,
        i.created_at,
        i.updated_at
    from invoices i
    left join order_totals ot
        on i.order_id = ot.order_id
)

select * from joined
