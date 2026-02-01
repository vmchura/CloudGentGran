{# Entry point macro #}
{% macro generate_years(start_year, end_year) %}
    {{ adapter.dispatch('generate_years', 'your_project')(start_year, end_year) }}
{% endmacro %}

{# DuckDB implementation #}
{% macro duckdb__generate_years(start_year, end_year) %}
    SELECT year
    FROM generate_series({{ start_year }}, {{ end_year }}) AS t(year)
{% endmacro %}

{# Athena implementation #}
{% macro athena__generate_years(start_year, end_year) %}
    SELECT year
    FROM UNNEST(sequence({{ start_year }}, {{ end_year }})) AS t(year)
{% endmacro %}

