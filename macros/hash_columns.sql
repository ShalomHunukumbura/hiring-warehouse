{#
  One md5 over several columns. A NULL becomes the text <null>, so ("a", NULL) and
  (NULL, "a") get different hashes.
#}
{% macro hash_columns(columns) -%}
  md5(concat_ws('|'
    {%- for column in columns %}, coalesce(cast({{ column }} as varchar), '<null>'){% endfor -%}
  ))
{%- endmacro %}
