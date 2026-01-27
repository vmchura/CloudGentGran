{{ adapter_aware_table_config() }}
SELECT
    service_qualification_id,
    service_type_id,
    comarca_id,
    municipal_id,
    EXTRACT(YEAR FROM inscription_date) AS year,
    EXTRACT(MONTH FROM inscription_date) AS month,
    SUM(capacity) AS total_capacit
FROM
    {{ read_staging_data ('social_services', 'downloaded_date', var ('downloaded_date')) }}
WHERE
    downloaded_date = '{{ var("downloaded_date") }}'
    AND capacity > 0
    AND service_type_id IN ('DAY-001', 'RES-003', 'RES-002', 'TUT-001', 'RES-001')
GROUP BY
    service_qualification_id,
    service_type_id,
    comarca_id,
    municipal_id,
    EXTRACT(YEAR FROM inscription_date),
    EXTRACT(MONTH FROM inscription_date)

