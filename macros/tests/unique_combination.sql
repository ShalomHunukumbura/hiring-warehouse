{#
  A generic test: no two rows share the same values in these columns. dbt-utils has one,
  but adding a package for a three-line query is not worth it.
#}
{% test unique_combination(model, columns) %}
select {{ columns | join(', ') }}, count(*) as rows
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}
