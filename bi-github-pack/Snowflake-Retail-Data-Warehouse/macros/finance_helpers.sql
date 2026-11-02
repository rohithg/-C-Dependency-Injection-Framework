{% macro cents_to_dollars(column_name, precision=2) -%}
  round(cast({{ column_name }} as decimal(18, 4)) / 100.0, {{ precision }})
{%- endmacro %}


{% macro safe_divide(numerator, denominator, default=0) -%}
  case
    when {{ denominator }} = 0 or {{ denominator }} is null then {{ default }}
    else cast({{ numerator }} as decimal(18, 6)) / cast({{ denominator }} as decimal(18, 6))
  end
{%- endmacro %}
