-- Day-over-day volume anomaly: flag when |delta| > 40% vs 7-day avg
with daily as (
  select cast(order_date as date) as d, count(*) as n
  from orders_dirty
  group by 1
),
stats as (
  select d, n,
         avg(n) over (order by d rows between 7 preceding and 1 preceding) as avg_7
  from daily
)
select * from stats
where avg_7 is not null and abs(n - avg_7) / avg_7 > 0.40;
