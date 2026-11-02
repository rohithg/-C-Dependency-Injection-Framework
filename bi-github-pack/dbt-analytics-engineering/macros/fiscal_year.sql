{% macro fiscal_year(date_expr, start_month=None) %}
{#
  Return fiscal year as an integer for a given timestamp/date expression.
  Fiscal year starts in `start_month` (default: project var fiscal_year_start_month).
  Example: start_month=2 means Feb 2024 – Jan 2025 => FY2024.
#}
{% set start_month = start_month if start_month is not none else var('fiscal_year_start_month', 2) %}
    case
        when extract(month from {{ date_expr }}) >= {{ start_month }}
            then extract(year from {{ date_expr }})
        else extract(year from {{ date_expr }}) - 1
    end
{% endmacro %}
