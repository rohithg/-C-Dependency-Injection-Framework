-- Load synthetic seeds into star schema (portable Postgres/Snowflake-ish)
truncate table energy_analytics.fct_energy_usage;
truncate table energy_analytics.dim_utility;
truncate table energy_analytics.dim_program;

insert into energy_analytics.dim_utility (utility_sk, utility_id, utility_name, state_code)
select row_number() over (order by utility_id), utility_id, utility_name, state
from (values
  ('U01','Pacific Gas Utility','CA'),
  ('U02','Desert Sun Electric','AZ'),
  ('U03','Rocky Mountain Power','CO'),
  ('U04','Great Lakes Energy','IL'),
  ('U05','Atlantic Coast Power','NJ')
) as v(utility_id, utility_name, state);

insert into energy_analytics.dim_program (program_sk, program_id, program_name, program_family)
select row_number() over (order by program_id), program_id, program_name,
       case when program_id like 'P_EE%' then 'EE'
            when program_id like 'P_DR%' then 'DR'
            when program_id like 'P_SR%' then 'Solar'
            else 'EV' end
from (values
  ('P_EE','Energy Efficiency'),
  ('P_DR','Demand Response'),
  ('P_SR','Solar Rebate'),
  ('P_EV','EV Charger Incentive')
) as v(program_id, program_name);

-- Date spine for 2024 H1
insert into energy_analytics.dim_date (date_sk, full_date, calendar_year, calendar_month, fiscal_year, season)
select
  cast(to_char(d, 'YYYYMMDD') as int),
  d,
  extract(year from d),
  extract(month from d),
  case when extract(month from d) >= 7 then extract(year from d)+1 else extract(year from d) end,
  case when extract(month from d) in (12,1,2) then 'Winter'
       when extract(month from d) in (3,4,5) then 'Spring'
       when extract(month from d) in (6,7,8) then 'Summer'
       else 'Fall' end
from generate_series(date '2024-01-01', date '2024-06-29', interval '1 day') as d;
