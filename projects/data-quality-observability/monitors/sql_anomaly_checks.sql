-- Portable SQL monitors (run against warehouse or DuckDB)
-- 1) Null email rate
select 'null_email_rate' as check_name,
       avg(case when email is null or email = '' then 1.0 else 0.0 end) as metric
from customers_dirty;

-- 2) Invalid amount rate
select 'negative_amount_rate' as check_name,
       avg(case when amount < 0 then 1.0 else 0.0 end) as metric
from orders_dirty;

-- 3) Invalid status rate
select 'invalid_status_rate' as check_name,
       avg(case when status not in ('OPEN','CLOSED','CANCELLED','PARTIAL') then 1.0 else 0.0 end) as metric
from orders_dirty;
