{{ config(
    materialized='incremental',
    incremental_strategy='insert_overwrite',
    partitioned_by=['downloaded_date'],
    external_location='s3://' ~ var('data_bucket') ~ '/marts/social_services_by_service_municipal'
) }}

SELECT
    service_qualification_id,
    service_type_id,
    comarca_id,
    municipal_id,
    EXTRACT(YEAR FROM inscription_date) as year,
    EXTRACT(MONTH FROM inscription_date) as month,
    SUM(capacity) as total_capacity,
    '{{ var("downloaded_date") }}' as downloaded_date
FROM {{ read_staging_data('social_services', 'downloaded_date', var('downloaded_date')) }}
WHERE downloaded_date = '{{ var("downloaded_date") }}' and
    capacity > 0 and
    service_type_id in ('DAY-001', 'RES-003', 'RES-002', 'TUT-001', 'RES-001')
GROUP BY
    service_qualification_id,
    service_type_id,
    comarca_id,
    municipal_id,
    EXTRACT(YEAR FROM inscription_date),
    EXTRACT(MONTH FROM inscription_date)