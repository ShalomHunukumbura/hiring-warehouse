{#
  By default dbt names schemas "<target schema>_<custom schema>", such as main_staging.
  Use the custom schema as it is (staging, intermediate), and main for the marts.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
  {{ custom_schema_name | trim if custom_schema_name else target.schema }}
{%- endmacro %}
