{{
  config(
    materialized='view',
    tags=['staging', 'erp', 'finance']
  )
}}

with source as (
    select * from {{ source('raw_erp', 'raw_invoices') }}
),

renamed as (
    select
        cast(invoice_id as varchar) as invoice_id,
        cast(invoice_number as varchar) as invoice_number,
        cast(order_id as varchar) as order_id,
        cast(customer_id as varchar) as customer_id,
        cast(nullif(trim(cast(invoice_date as varchar)), '') as date) as invoice_date,
        cast(nullif(trim(cast(due_date as varchar)), '') as date) as due_date,
        cast(nullif(trim(cast(paid_date as varchar)), '') as date) as paid_date,
        upper(trim(invoice_status)) as invoice_status,
        cast(subtotal_amount as decimal(18, 2)) as subtotal_amount,
        cast(tax_amount as decimal(18, 2)) as tax_amount,
        cast(freight_amount as decimal(18, 2)) as freight_amount,
        cast(total_amount as decimal(18, 2)) as total_amount,
        cast(amount_paid as decimal(18, 2)) as amount_paid,
        trim(currency_code) as currency_code,
        cast(payment_terms_days as integer) as payment_terms_days,
        cast(created_at as timestamp) as created_at,
        cast(updated_at as timestamp) as updated_at,
        cast(_loaded_at as timestamp) as _loaded_at,
        cast(_source_system as varchar) as _source_system
    from source
),

enriched as (
    select
        *,
        round(coalesce(total_amount, 0) - coalesce(amount_paid, 0), 2) as balance_due,
        case
            when upper(invoice_status) = 'PAID' then 0
            when due_date < current_date and coalesce(amount_paid, 0) < coalesce(total_amount, 0) then 1
            else 0
        end as is_overdue,
        case
            when paid_date is not null and invoice_date is not null
            then cast(paid_date as date) - cast(invoice_date as date)
            else null
        end as days_to_pay,
        row_number() over (
            partition by invoice_id
            order by updated_at desc, _loaded_at desc
        ) as _row_num
    from renamed
)

select
    invoice_id,
    invoice_number,
    order_id,
    customer_id,
    invoice_date,
    due_date,
    paid_date,
    invoice_status,
    subtotal_amount,
    tax_amount,
    freight_amount,
    total_amount,
    amount_paid,
    balance_due,
    is_overdue,
    days_to_pay,
    currency_code,
    payment_terms_days,
    created_at,
    updated_at,
    _loaded_at,
    _source_system
from enriched
where _row_num = 1
