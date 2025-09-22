-- Mart: Social Services - Simple pass-through for testing
-- This model creates the final mart table from staging data

SELECT
    service_qualification_id,
    service_type_id,
    comarca_id,
    municipal_id,
    EXTRACT(YEAR FROM inscription_date) as year,
    EXTRACT(MONTH FROM inscription_date) as month,
    SUM(capacity) as capacity
FROM {{ ref('src_social_services') }}
WHERE capacity > 0 and
    service_type_id in ('DAY-001', 'RES-003', 'RES-002', 'TUT-001', 'RES-001')
GROUP BY service_qualification_id,
             service_type_id,
             comarca_id,
             municipal_id,
             EXTRACT(YEAR FROM inscription_date),
             EXTRACT(MONTH FROM inscription_date)