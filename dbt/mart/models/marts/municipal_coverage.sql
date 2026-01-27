{{ adapter_aware_table_config() }}
WITH municipals AS (
    SELECT DISTINCT
        codi AS municipal_id
    FROM
        {{ read_catalog_data ('municipals') }}
),
-- Generate series of years from 1975 to 2025 for Athena

year_series AS (
	{{generate_years(1975, 2026)}}
),
all_combinations AS (
    SELECT
        m.municipal_id,
        y.year
    FROM
        municipals AS m
        CROSS JOIN year_series y
),
-- Read population data and rename columns for consistency
renamed_population AS (
    SELECT
        municipal_code AS municipal_id,
        year,
        population,
        population_ge65
    FROM
        {{ read_marts_data ('population_municipal_greater_65') }}
),
joined_population AS (
    SELECT
        a.municipal_id,
        a.year,
        p.population,
        p.population_ge65
    FROM
        all_combinations AS a
        LEFT JOIN renamed_population AS p ON a.municipal_id = p.municipal_id
            AND a.year = p.year
),
filled_population AS (
    SELECT
        municipal_id,
        year,
	{{forward_fill('population', 'municipal_id', 'year')}} AS population,
	{{forward_fill('population_ge65', 'municipal_id', 'year')}} AS population_ge65
FROM
    joined_population
),
-- Filter for residence services only
social_services_residence AS (
    SELECT
        *
    FROM
        {{ ref ('social_services_by_service_municipal') }}
    WHERE
        service_type_id = 'RES-003'
),
joined_social_services AS (
    SELECT
        a.municipal_id,
        a.year,
        ss.total_capacit
    FROM
        all_combinations AS a
        LEFT JOIN social_services_residence AS ss ON a.municipal_id = ss.municipal_id
            AND a.year = ss.year
),
filled_social_services AS (
    SELECT
        municipal_id,
        year,
        -- Cumulative sum of capacity over time
        SUM(total_capacit) OVER (PARTITION BY municipal_id ORDER BY year ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS total_capacit
    FROM
        joined_social_services
),
clean_filled_social_services AS (
    SELECT
        *
    FROM
        filled_social_services
    WHERE
        total_capacit IS NOT NULL
),
complete_data AS (
    SELECT
        *
    FROM
        filled_population p
        JOIN clean_filled_social_services ss USING (municipal_id, year)
),
with_coverage AS (
    SELECT
        municipal_id,
        year,
        total_capacit,
        population_ge65,
        total_capacit * 100.0 / population_ge65 AS coverage_ratio
    FROM
        complete_data
)
SELECT
    municipal_id,
    year,
    total_capacit,
    population_ge65,
    ROUND(coverage_ratio, 2) AS coverage_ratio
FROM
    with_coverage
ORDER BY
    municipal_id,
    year

