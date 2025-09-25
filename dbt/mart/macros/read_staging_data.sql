{% macro read_staging_data(table_name, partition_key, partition_value) %}
    read_parquet('{{ "" if target.name == "local" else "s3://" }}{{ var("data_bucket") }}/staging/{{ table_name }}/{{ partition_key }}={{ partition_value }}/*.parquet')
{% endmacro %}
