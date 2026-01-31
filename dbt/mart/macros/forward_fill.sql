{% macro forward_fill(expr, partition_by, order_by) %}
  {{ adapter.dispatch('forward_fill', 'your_project')(expr, partition_by, order_by) }}
{% endmacro %}

{% macro duckdb__forward_fill(expr, partition_by, order_by) %}
  LAST_VALUE({{ expr }} IGNORE NULLS)
  OVER (PARTITION BY {{ partition_by }} ORDER BY {{ order_by }}
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
{% endmacro %}

{% macro athena__forward_fill(expr, partition_by, order_by) %}

MAX(
  CASE
    WHEN {{ order_by }} = 
      MAX(
        CASE
          WHEN {{ expr }} IS NOT NULL THEN {{ order_by }}
        END
      ) OVER (
        PARTITION BY {{ partition_by }}
        ORDER BY {{ order_by }}
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
      )
    THEN {{ expr }}
  END
)
OVER (
  PARTITION BY {{ partition_by }}
  ORDER BY {{ order_by }}
  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
)

{% endmacro %}

