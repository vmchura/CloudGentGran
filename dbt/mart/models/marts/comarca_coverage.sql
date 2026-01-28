{{ adapter_aware_table_config() }}
WITH comarcas AS (
  SELECT DISTINCT comarca_id
  FROM {{ read_catalog_data('municipals') }}
),

-- Generate series of years from 1975 to 2025 for Athena
year_series AS (
	{{generate_years(1975, 2025)}}
),

all_combinations AS (
  SELECT c.comarca_id, y.year
  FROM comarcas AS c
  CROSS JOIN year_series y
),

joined_population AS (
  SELECT
    a.comarca_id,
    a.year,
    p.population,
    p.population_age_65_and_over
  FROM all_combinations AS a
  LEFT JOIN {{ ref('comarca_population') }} p
    USING (comarca_id, year)
),

filled_population AS (
  SELECT
    comarca_id,
    year,
    -- Forward fill population using LAST_VALUE window function
    {{forward_fill('population', 'comarca_id', 'year')}} AS population,
    {{forward_fill('population_age_65_and_over', 'comarca_id', 'year')}} AS population_age_65_and_over,
  FROM joined_population
),

-- Filter for residence services only and aggregate by comarca
social_services_residence AS (
  SELECT 
    comarca_id,
    year,
    total_capacit
  FROM {{ ref('social_services_by_service_municipal') }}
  WHERE service_type_id = 'RES-003'
),

-- Aggregate social services by comarca and year
social_services_comarca AS (
  SELECT 
    comarca_id,
    year,
    SUM(total_capacit) as total_capacit
  FROM social_services_residence
  GROUP BY comarca_id, year
),

joined_social_services AS (
  SELECT
    a.comarca_id,
    a.year,
    ss.total_capacit
  FROM all_combinations AS a
  LEFT JOIN social_services_comarca ss
    USING (comarca_id, year)
),

filled_social_services AS (
  SELECT
    comarca_id,
    year,
    -- Cumulative sum of capacity over time
    SUM(total_capacit)
      OVER (
        PARTITION BY comarca_id
        ORDER BY year
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
      ) AS total_capacit
  FROM joined_social_services
),

clean_filled_social_services AS (
  SELECT * 
  FROM filled_social_services 
  WHERE total_capacit IS NOT NULL
),

complete_data AS (
  SELECT *
  FROM filled_population p
  JOIN clean_filled_social_services ss
    USING (comarca_id, year)
),

with_coverage AS (
  SELECT 
    comarca_id, 
    year, 
    total_capacit, 
    population_age_65_and_over, 
    total_capacit * 100.0 / population_age_65_and_over as coverage_ratio 
  FROM complete_data
)

SELECT 
  comarca_id, 
  year,
  total_capacit,
  population_age_65_and_over,
  ROUND(coverage_ratio, 2) as coverage_ratio 
FROM with_coverage 
ORDER BY comarca_id, year
