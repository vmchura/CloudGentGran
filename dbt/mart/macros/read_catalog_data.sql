{% macro read_catalog_data(table_name) %}
    {% if target.name == "local" %}
        read_parquet('s3://{{ var("catalog_bucket") }}/{{ table_name }}/*.parquet')
    {% else %}
        {{ source('catalog', table_name) }}
    {% endif %}
{% endmacro %}
