{% macro safe_divide(numerator, denominator) %}
{#
  Division that returns null when the denominator is zero or null.
  Prefer null over infinity / DIV0 errors.
#}
    case
        when ({{ denominator }}) = 0 or ({{ denominator }}) is null then null
        else cast(({{ numerator }}) as {{ dbt.type_float() }}) / cast(({{ denominator }}) as {{ dbt.type_float() }})
    end
{% endmacro %}
