-- Mart: Social Services - Simple pass-through for testing
-- This model creates the final mart table from staging data

{% if target.name == 'prod' %}
{{ config(
    materialized='table',
    description='Social services mart - testing DBT setup',
    file_format='parquet',
    location_root='s3://catalunya-data-prod/marts/social_services/'
) }}
{% else %}
{{ config(
    materialized='table',
    description='Social services mart - testing DBT setup'
) }}
{% endif %}

SELECT 
    *,
    CURRENT_TIMESTAMP as dbt_created_at,
    '{{ target.name }}' as environment
FROM {{ ref('src_social_services') }}