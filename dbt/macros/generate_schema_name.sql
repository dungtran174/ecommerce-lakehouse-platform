{#
    Custom macro to override dbt default schema naming.
    By default, dbt prefixes custom schema with target.schema (e.g., default_silver).
    This macro ensures the exact custom schema name is used without prefix (e.g., silver, sale_mart).
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set default_schema = target.schema -%}
    {%- if custom_schema_name is none -%}
        {{ default_schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
