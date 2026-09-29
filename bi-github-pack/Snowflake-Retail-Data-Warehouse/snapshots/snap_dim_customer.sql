{% snapshot snap_dim_customer %}
{{
  config(
    target_schema='snapshots',
    unique_key='customer_nk',
    strategy='timestamp',
    updated_at='customer_updated_at',
    invalidate_hard_deletes=True,
    tags=['snapshot', 'scd2']
  )
}}

-- Type-2 history for customer attributes Finance and Sales both care about
-- (credit limit, status, account manager). Mart dim_customer stays current-state;
-- this snapshot preserves change history for audit / churn analysis.

select
    customer_nk,
    customer_code,
    customer_name,
    customer_type,
    industry,
    status,
    credit_limit,
    account_manager,
    billing_state,
    billing_country,
    customer_updated_at
from {{ ref('dim_customer') }}

{% endsnapshot %}
