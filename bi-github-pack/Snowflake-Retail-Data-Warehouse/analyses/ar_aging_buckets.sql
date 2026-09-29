-- AR aging buckets aligned to the executive semantic-layer story.

with open_invoices as (
    select
        invoice_nk,
        customer_sk,
        invoice_date,
        due_date,
        invoice_status,
        balance_due,
        datediff('day', due_date, current_date()) as days_past_due
    from {{ ref('fct_finance') }}
    where invoice_status in ('OPEN', 'PARTIAL', 'OVERDUE')
       or balance_due > 0
)

select
    case
        when days_past_due <= 0 then 'Current'
        when days_past_due between 1 and 30 then '1–30'
        when days_past_due between 31 and 60 then '31–60'
        when days_past_due between 61 and 90 then '61–90'
        else '90+'
    end as aging_bucket,
    count(*) as invoice_count,
    sum(balance_due) as open_ar
from open_invoices
group by 1
order by
    case aging_bucket
        when 'Current' then 1
        when '1–30' then 2
        when '31–60' then 3
        when '61–90' then 4
        else 5
    end
