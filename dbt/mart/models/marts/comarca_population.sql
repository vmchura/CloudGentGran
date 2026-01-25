{{config(materialized='external',
format = 'parquet',
location = "s3://{{ env_var('DATA_BUCKET') }}/marts/{{this.name}}",
options = { "per_thread_output" : true }) }}

WITH population_with_comarca AS (
  SELECT 
    p.population_ge65, 
    p.population, 
    p.year, 
    m.codi_comarca
  FROM {{ read_marts_data('population_municipal_greater_65') }} p
  JOIN {{ read_catalog_data('municipals') }} m 
    ON p.municipal_code = m.codi
),

comarca_population_aggregated AS (
  SELECT 
    p.codi_comarca as comarca_id,
    SUM(p.population_ge65) as population_ge65,
    SUM(p.population) as population,
    ROUND(SUM(p.population_ge65) * 100.0 / SUM(p.population), 2) as elderly_indicator,
    p.year
  FROM population_with_comarca p
  GROUP BY p.codi_comarca, p.year
)

SELECT 
  comarca_id,
  population_ge65,
  year,
  population,
  elderly_indicator
FROM comarca_population_aggregated 
ORDER BY comarca_id, year
