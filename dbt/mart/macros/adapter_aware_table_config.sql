{% macro adapter_aware_table_config() %}
  {% if target.type == 'duckdb' %}

    {{ config(
        materialized = 'external',
	format = 'parquet',
	location = "s3://{{ env_var('DATA_BUCKET') }}/marts/{{this.name}}",
	options = { "per_thread_output" : true, "overwrite_or_ignore" : true }
    ) }}

  {% else %}

    {{ config(
        materialized = 'table'
    ) }}

  {% endif %}
{% endmacro %}

