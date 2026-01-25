{{config(materialized='external',
format = 'parquet',
location = "s3://{{ env_var('DATA_BUCKET') }}/marts/{{this.name}}",
options = { "per_thread_output" : true }) }}
WITH municipals AS (
    SELECT DISTINCT
        codi AS municipal_id,
        codi_comarca
    FROM
        {{ read_catalog_data ('municipals') }}
),
social_service_types AS (
    SELECT DISTINCT
        service_type_id
    FROM
        {{ ref ('social_services_by_service_municipal') }}
),
service_qualification_types AS (
    SELECT DISTINCT
        service_qualification_id
    FROM
        {{ ref ('social_services_by_service_municipal') }}
),
relevant_combinations AS (
    SELECT DISTINCT
        municipal_id,
        service_type_id,
        service_qualification_id
    FROM
        {{ ref ('social_services_by_service_municipal') }}
    WHERE
        total_capacit > 0
),
year_series AS (
    {{ generate_years(1975, 2026) }}
),
all_combinations AS (
    SELECT
        rc.municipal_id,
        rc.service_type_id,
        rc.service_qualification_id,
        m.codi_comarca,
        y.year
    FROM
        relevant_combinations rc
        JOIN municipals m ON rc.municipal_id = m.municipal_id
        CROSS JOIN year_series y
),
joined AS (
    SELECT
        ac.municipal_id,
        ac.service_type_id,
        ac.service_qualification_id,
        ac.codi_comarca AS comarca_id,
        ac.year,
        COALESCE(ss.total_capacit, 0) AS total_capacit
    FROM
        all_combinations ac
        LEFT JOIN {{ ref ('social_services_by_service_municipal') }} ss ON ac.municipal_id = ss.municipal_id
            AND ac.service_type_id = ss.service_type_id
            AND ac.service_qualification_id = ss.service_qualification_id
            AND ac.year = ss.year
),
first_nonzero AS (
    SELECT
        municipal_id,
        service_type_id,
        service_qualification_id,
        MIN(year) AS first_year
    FROM
        joined
    WHERE
        total_capacit > 0
    GROUP BY
        municipal_id,
        service_type_id,
        service_qualification_id
)
SELECT
    j.municipal_id,
    j.service_type_id,
    j.service_qualification_id,
    j.comarca_id,
    j.year,
    j.total_capacit
FROM
    joined j
    JOIN first_nonzero f ON j.municipal_id = f.municipal_id
        AND j.service_type_id = f.service_type_id
        AND j.service_qualification_id = f.service_qualification_id
WHERE
    j.year >= f.first_year
ORDER BY
    j.year,
    j.comarca_id,
    j.municipal_id,
    j.service_type_id

