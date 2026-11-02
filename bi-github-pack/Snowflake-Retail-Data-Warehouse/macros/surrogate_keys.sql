{% macro generate_surrogate_key(field_list) -%}
  {#- Deterministic surrogate key from natural-key column(s). -#}
  {%- set fields = [] -%}
  {%- for field in field_list -%}
    {%- do fields.append(
      "coalesce(cast(" ~ field ~ " as varchar), '_null_')"
    ) -%}
  {%- endfor -%}
  md5({{ fields | join(" || '|' || ") }})
{%- endmacro %}


{% macro generate_schema_name(custom_schema_name, node) -%}
  {#-
    Honor custom schemas (staging, intermediate, marts, raw) so seed tables
    align with source() definitions on both Snowflake and DuckDB.
  -#}
  {%- set default_schema = target.schema -%}
  {%- if custom_schema_name is none -%}
    {{ default_schema }}
  {%- else -%}
    {{ custom_schema_name | trim }}
  {%- endif -%}
{%- endmacro %}
