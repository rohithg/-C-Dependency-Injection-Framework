-- Monthly compliance & demand mart used by Power BI DirectQuery / import
create or replace view energy_analytics.mart_monthly_program_performance as
select
  d.calendar_year,
  d.calendar_month,
  u.utility_name,
  u.state_code,
  p.program_name,
  sum(f.kwh) as total_kwh,
  max(f.peak_kw) as peak_kw,
  sum(f.customer_count) as participating_customers,
  sum(f.incentive_paid_usd) as incentive_spend,
  avg(case when f.is_compliant then 1.0 else 0.0 end) as compliance_rate
from energy_analytics.fct_energy_usage f
join energy_analytics.dim_date d on f.date_sk = d.date_sk
join energy_analytics.dim_utility u on f.utility_sk = u.utility_sk
join energy_analytics.dim_program p on f.program_sk = p.program_sk
group by 1,2,3,4,5;
