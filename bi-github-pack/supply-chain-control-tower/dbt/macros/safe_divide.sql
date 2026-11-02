{% macro safe_divide(n, d) %}
  case when {{ d }} = 0 or {{ d }} is null then null else {{ n }} / {{ d }} end
{% endmacro %}
