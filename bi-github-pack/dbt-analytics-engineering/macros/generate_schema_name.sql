{% macro generate_schema_name(custom_schema_name, node) -%}
{# Keep custom schemas as-is under the target schema prefix for CI isolation. #}
    {%- set default_schema = target.schema -%}
    {%- if custom_schema_name is none -%}
        {{ default_schema }}
    {%- else -%}
        {{ default_schema }}_{{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
