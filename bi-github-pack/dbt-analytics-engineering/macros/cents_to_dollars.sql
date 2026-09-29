{% macro cents_to_dollars(column_name, scale=2) %}
{#
  Convert integer cents to decimal dollars.
  Uses dbt cross-db numeric typing; Snowflake-compatible.
#}
    round(cast({{ column_name }} as {{ dbt.type_numeric() }}) / 100, {{ scale }})
{% endmacro %}
