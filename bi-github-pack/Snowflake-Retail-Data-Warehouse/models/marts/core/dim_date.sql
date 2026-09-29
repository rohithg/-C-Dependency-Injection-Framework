{{
  config(
    materialized='table',
    tags=['marts', 'dimension', 'calendar']
  )
}}

with date_spine as (
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('" ~ var('start_date') ~ "' as date)",
        end_date="cast('" ~ var('end_date') ~ "' as date)"
    ) }}
),

calendar as (
    select cast(date_day as date) as date_day
    from date_spine
)

select
    cast(
        extract(year from date_day) * 10000
        + extract(month from date_day) * 100
        + extract(day from date_day)
        as integer
    ) as date_sk,
    date_day,
    cast(extract(year from date_day) as integer) as year_number,
    cast(extract(quarter from date_day) as integer) as quarter_number,
    cast(extract(month from date_day) as integer) as month_number,
    cast(extract(day from date_day) as integer) as day_of_month,
    cast(extract(dow from date_day) as integer) as day_of_week,
    cast(extract(year from date_day) as varchar)
        || '-'
        || lpad(cast(cast(extract(month from date_day) as integer) as varchar), 2, '0') as year_month,
    case cast(extract(month from date_day) as integer)
        when 1 then 'January' when 2 then 'February' when 3 then 'March'
        when 4 then 'April' when 5 then 'May' when 6 then 'June'
        when 7 then 'July' when 8 then 'August' when 9 then 'September'
        when 10 then 'October' when 11 then 'November' when 12 then 'December'
    end as month_name,
    case cast(extract(dow from date_day) as integer)
        when 0 then 'Sunday' when 1 then 'Monday' when 2 then 'Tuesday'
        when 3 then 'Wednesday' when 4 then 'Thursday' when 5 then 'Friday'
        when 6 then 'Saturday'
    end as day_name,
    case
        when cast(extract(dow from date_day) as integer) in (0, 6) then true
        else false
    end as is_weekend,
    case
        when cast(extract(month from date_day) as integer) >= 2
        then cast(extract(year from date_day) as integer)
        else cast(extract(year from date_day) as integer) - 1
    end as fiscal_year,
    case
        when cast(extract(month from date_day) as integer) in (2, 3, 4) then 1
        when cast(extract(month from date_day) as integer) in (5, 6, 7) then 2
        when cast(extract(month from date_day) as integer) in (8, 9, 10) then 3
        else 4
    end as fiscal_quarter,
    current_timestamp as dbt_updated_at
from calendar
