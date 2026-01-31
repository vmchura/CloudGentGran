{% macro forward_fill(expr, partition_by, order_by) %}
  {{ adapter.dispatch('forward_fill', 'your_project')(expr, partition_by, order_by) }}
{% endmacro %}

{% macro duckdb__forward_fill(expr, partition_by, order_by) %}
  LAST_VALUE({{ expr }} IGNORE NULLS)
  OVER (PARTITION BY {{ partition_by }} ORDER BY {{ order_by }}
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
{% endmacro %}

{% macro athena__forward_fill(expr, partition_by, order_by) %}
  max_by({{ expr }}, {{ order_by }})
  FILTER (WHERE {{ expr }} IS NOT NULL)
  OVER (
    PARTITION BY {{ partition_by }}
    ORDER BY {{ order_by }}
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  )
{% endmacro %}

