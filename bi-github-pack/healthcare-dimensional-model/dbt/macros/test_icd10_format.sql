{# Macro: simplified ICD-10-CM format check for reusable tests #}
{% test icd10_format(model, column_name) %}

select
    {{ column_name }} as invalid_icd10_cd
from {{ model }}
where {{ column_name }} is not null
  and {{ column_name }} !~ '^[A-TV-Z][0-9][0-9A-Z](\.[0-9A-Z]{1,4})?$'

{% endtest %}
