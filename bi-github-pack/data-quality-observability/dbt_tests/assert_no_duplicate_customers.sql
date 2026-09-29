-- Singular dbt test: customer natural key uniqueness
select customer_id, count(*) as n
from {{ ref('stg_customers') }}
group by 1
having count(*) > 1
