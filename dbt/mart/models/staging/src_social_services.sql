-- Source: Social Services raw data from staging layer
-- Local development: reads from local folder
-- Production: reads from S3 staging layer

{{ config(
    materialized='view',
    description='Raw social services data from staging layer'
) }}

{% if target.name == 'dev' %}
    -- Local development: read from local folder structure
    SELECT * FROM read_parquet('{{ var("staging_path") }}/social_services/*.parquet')
{% else %}
    -- Production: read from S3 staging layer
    SELECT * FROM read_parquet('s3://catalunya-data-prod/staging/social_services/*.parquet')
{% endif %}