-- Source: Social Services raw data from staging layer
-- Local development: reads from local folder
-- Production: reads from S3 staging layer

{{ config(
    materialized='view',
    description='Raw social services data from staging layer'
) }}

{% if target.name == 'local' %}
    -- Local development: read from local folder structure
    SELECT * FROM read_parquet(
        '{{ var("staging_path") }}/social_services/downloaded_date={{ var("downloaded_date") }}/*.parquet'
    )
{% else %}
    -- Production/LocalStack: read from S3 staging layer via LocalStack
    SELECT * FROM read_parquet(
        's3://catalunya-data-dev/staging/social_services/downloaded_date={{ var("downloaded_date") }}/*.parquet'
    )
{% endif %}
