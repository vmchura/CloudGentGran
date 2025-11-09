{% macro read_staging_data(table_name, partition_key, partition_value) %}
    {% if target.name == "local" %}
        -- DuckDB: Read directly from parquet files
        read_parquet('{{ var("data_bucket") }}/staging/{{ table_name }}/{{ partition_key }}={{ partition_value }}/*.parquet')
    {% else %}
        -- Athena: Use source table with partition filter
        {{ source('staging', table_name) }}
    {% endif %}
{% endmacro %}