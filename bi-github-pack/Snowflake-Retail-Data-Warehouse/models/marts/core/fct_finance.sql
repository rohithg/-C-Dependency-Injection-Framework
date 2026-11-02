{{
  config(
    materialized='table',
    tags=['marts', 'fact', 'finance']
  )
}}

with invoices as (
    select * from {{ ref('int_invoice_order_bridge') }}
),

customers as (
    select customer_sk, customer_nk from {{ ref('dim_customer') }}
),

invoice_dates as (
    select date_sk, date_day from {{ ref('dim_date') }}
),

due_dates as (
    select date_sk, date_day from {{ ref('dim_date') }}
),

paid_dates as (
    select date_sk, date_day from {{ ref('dim_date') }}
)

select
    {{ generate_surrogate_key(['i.invoice_id']) }} as invoice_sk,
    i.invoice_id as invoice_nk,
    i.invoice_number,
    i.order_id,
    c.customer_sk,
    id.date_sk as invoice_date_sk,
    dd.date_sk as due_date_sk,
    pd.date_sk as paid_date_sk,
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
    i.collection_rate,
    i.currency_code,
    i.payment_terms_days,
    i.order_net_amount,
    i.order_gross_amount,
    i.order_cogs,
    i.order_gross_margin,
    i.order_line_count,
    i.created_at,
    i.updated_at,
    current_timestamp as dbt_updated_at
from invoices i
left join customers c on i.customer_id = c.customer_nk
left join invoice_dates id on i.invoice_date = id.date_day
left join due_dates dd on i.due_date = dd.date_day
left join paid_dates pd on i.paid_date = pd.date_day
