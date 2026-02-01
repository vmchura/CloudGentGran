{% macro read_marts_data(table_name) %}
    {% if target.name == "local" %}
        read_parquet('s3://{{ var("data_bucket") }}/marts/{{ table_name }}/*.parquet')
    {% else %}
        {{ source('marts', table_name) }}
    {% endif %}
{% endmacro %}
