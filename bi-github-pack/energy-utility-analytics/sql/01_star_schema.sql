-- Energy / utility analytics star schema (portfolio — synthetic)
create schema if not exists energy_analytics;

create table energy_analytics.dim_utility (
  utility_sk int primary key,
  utility_id varchar(16) not null unique,
  utility_name varchar(128),
  state_code char(2)
);

create table energy_analytics.dim_program (
  program_sk int primary key,
  program_id varchar(16) not null unique,
  program_name varchar(128),
  program_family varchar(64) -- EE, DR, Solar, EV
);

create table energy_analytics.dim_date (
  date_sk int primary key,
  full_date date not null unique,
  calendar_year int,
  calendar_month int,
  fiscal_year int,
  season varchar(16)
);

create table energy_analytics.fct_energy_usage (
  usage_sk bigint primary key,
  date_sk int references energy_analytics.dim_date(date_sk),
  utility_sk int references energy_analytics.dim_utility(utility_sk),
  program_sk int references energy_analytics.dim_program(program_sk),
  kwh numeric(18,2),
  peak_kw numeric(18,2),
  customer_count int,
  incentive_paid_usd numeric(18,2),
  is_compliant boolean,
  grain_note varchar(64) default 'utility × program × day'
);

create index ix_fct_usage_date on energy_analytics.fct_energy_usage(date_sk);
create index ix_fct_usage_utility on energy_analytics.fct_energy_usage(utility_sk);
