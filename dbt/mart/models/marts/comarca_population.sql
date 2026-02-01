{{ adapter_aware_table_config() }}
WITH population_with_comarca AS (
  SELECT 
    p.population_age_65_and_over, 
    p.population, 
    p.year, 
    m.comarca_id
  FROM {{ read_marts_data('municipal_population') }} p
  JOIN {{ read_catalog_data('municipals') }} m 
    ON p.municipal_id = m.municipal_id
),

comarca_population_aggregated AS (
  SELECT 
    p.comarca_id,
    SUM(p.population_age_65_and_over) as population_age_65_and_over,
    SUM(p.population) as population,
    ROUND(SUM(p.population_age_65_and_over) * 100.0 / SUM(p.population), 2) as elderly_indicator,
    p.year
  FROM population_with_comarca p
  GROUP BY p.comarca_id, p.year
)

SELECT 
  comarca_id,
  population_age_65_and_over,
  year,
  population,
  elderly_indicator
FROM comarca_population_aggregated 
ORDER BY comarca_id, year
