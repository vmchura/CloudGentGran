import { DuckDBInstance } from '@duckdb/node-api';


import JSZip from "jszip";

const isLocal = process.env.AWS_PROFILE === "localstack";
const BUCKET_DATA = process.env.S3_BUCKET_DATA;
const BUCKET_CATALOG = process.env.S3_BUCKET_CATALOG;

console.error(`Using bucket data: ${BUCKET_DATA}: bucket catalog: ${BUCKET_CATALOG} (local: ${isLocal})`);

const instance = await DuckDBInstance.create(':memory:');
const conn = await instance.connect();
console.error(`Connected`);

// Set up S3 + httpfs
await conn.run("INSTALL httpfs;");
console.error(`INSTALL httpfs`);

await conn.run("LOAD httpfs;");
console.error(`LOAD httpfs`);

if (isLocal) {
  console.error("Using LocalStack credentials");
  await conn.run(`
    CREATE OR REPLACE SECRET localstack_s3 (
      TYPE S3,
      KEY_ID 'test',
      SECRET 'test',
      REGION 'eu-west-1',
      ENDPOINT 'localhost:4566',
      URL_STYLE 'path',
      USE_SSL false
    );
  `);
} else {
  console.error("Using AWS default credential chain");
  conn.run(`
    CREATE OR REPLACE SECRET aws_s3 (
      TYPE S3,
      PROVIDER credential_chain
    );
  `);
}

// Load data
await conn.run(`
    CREATE TABLE population AS
    SELECT * FROM read_parquet('s3://${BUCKET_DATA}/marts/population_municipal_greater_65/population_municipal_greater_65.parquet');
    CREATE TABLE municipal AS
    SELECT * FROM read_parquet('s3://${BUCKET_CATALOG}/municipals/*');
    CREATE TABLE social_services AS
    SELECT * FROM read_parquet('s3://${BUCKET_DATA}/marts/social_services_by_service_municipal/*');`);

console.error(`Processing: social_services_empty_last_year`);
await conn.run(`CREATE TABLE social_services_empty_last_year as 
      WITH municipals AS (
        SELECT DISTINCT codi AS municipal_id, codi_comarca
        FROM municipal
      ),
      social_service_types AS (
        SELECT DISTINCT service_type_id
        FROM social_services
      ),
      all_combinations AS (
        SELECT m.municipal_id, ss.service_type_id, m.codi_comarca, 2025 as year
        FROM municipals AS m
        CROSS JOIN social_service_types AS ss
      ),
      joined_social_services AS (
        SELECT
          COALESCE(a.municipal_id, ss.municipal_id) as municipal_id,
          COALESCE(a.service_type_id, ss.service_type_id) as service_type_id,
          COALESCE(a.year, ss.year) as year,
          COALESCE(ss.total_capacit, 0) as total_capacit,
          COALESCE(a.codi_comarca, ss.comarca_id) as comarca_id,
        FROM social_services AS ss
        FULL JOIN all_combinations AS a
        USING (municipal_id, service_type_id, year)
      )
      select municipal_id, service_type_id, CAST(year as INT) as year, CAST(total_capacit as INT) as total_capacit, comarca_id from joined_social_services;`);

console.error(`Processing: municipal_coverage`);
await conn.run(`CREATE TABLE municipal_coverage as 
      WITH municipals AS (
        SELECT DISTINCT codi AS municipal_id
        FROM municipal
      ),
      year_bounds AS (
        SELECT MIN(year) AS min_year, MAX(year) AS max_year
        FROM population
      ),
      all_combinations AS (
        SELECT m.municipal_id, y.year
        FROM municipals AS m
        CROSS JOIN generate_series(1975, 2025) AS y(year)
      ),
        renamed_population as (
        select p.municipal_code as municipal_id,
        p.year, p.population, p.population_ge65 from population as p
        ),
        
        joined_population AS (
        SELECT
          a.municipal_id,
          a.year,
          p.population,
          p.population_ge65
        FROM all_combinations AS a
        LEFT JOIN renamed_population AS p
        USING (municipal_id, year)
      ),
        filled_population AS (
        SELECT
          municipal_id,
          year,
          LAST_VALUE(population IGNORE NULLS)
            OVER (PARTITION BY municipal_id ORDER BY year ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
            AS population,
          LAST_VALUE(population_ge65 IGNORE NULLS)
            OVER (PARTITION BY municipal_id ORDER BY year ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
            AS population_ge65
        FROM joined_population
      ),
        social_services_residence as (select * from social_services where service_type_id='RES-003'),
        joined_social_services AS (
        SELECT
          a.municipal_id,
          a.year,
          ss.total_capacit,
        ss.service_type_id
        FROM all_combinations AS a
        LEFT JOIN social_services_residence AS ss
        USING (municipal_id, year)
      ),
        filled_social_services AS (
        SELECT
          municipal_id,
          year,
          SUM(total_capacit)
            OVER (
              PARTITION BY municipal_id
              ORDER BY year
              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS total_capacit
        FROM joined_social_services
      ),
        clean_filled_social_services AS (select * from filled_social_services where total_capacit is NOT NULL),
      complete_data as (
        select * from
        filled_population as p
        JOIN clean_filled_social_services as ss
        USING (municipal_id, year)
      ),
        with_coverage as (
        select municipal_id, year, total_capacit*100.0 / population_ge65 as coverage_ratio from complete_data
        )
      select municipal_id, CAST(year as INT) as year, ROUND(coverage_ratio, 2) as coverage_ratio from with_coverage order by municipal_id, year;`);

console.error(`Processing: comarca_population`);      
await conn.run(`CREATE TABLE comarca_population as
        WITH population_with_comarca as (
          select p.population_ge65 , p.population, p.year, m.codi_comarca
        from population as p
        join municipal as m on p.municipal_code = m.codi
          ),
        comarca_population_aggregated AS (
        select p.codi_comarca as comarca_id,
        SUM(p.population_ge65) as population_ge65,
        SUM(p.population) as 'population',
        ROUND(SUM(p.population_ge65) / SUM(p.population), 2) as elderly_indicator,
        p.year
        from population_with_comarca p
        GROUP BY p.codi_comarca, p.year
        )
        select comarca_id,
        CAST(population_ge65 as INT) as population_ge65,
        cast(year as INT) as year,
        CAST(population as INT) as population,
        elderly_indicator
        from comarca_population_aggregated order by comarca_id, year;`);

console.error(`Processing: comarca_coverage`);      
await conn.run(`CREATE TABLE comarca_coverage as 
          WITH comarcas AS (
            SELECT DISTINCT codi_comarca AS comarca_id
            FROM municipal
          ),
          year_bounds AS (
            SELECT MIN(year) AS min_year, MAX(year) AS max_year
            FROM population
          ),
          all_combinations AS (
            SELECT c.comarca_id, y.year
            FROM comarcas AS c
            CROSS JOIN generate_series(1975, 2025) AS y(year)
          ),
            joined_population AS (
            SELECT
              a.comarca_id,
              a.year,
              p.population,
              p.population_ge65
            FROM all_combinations AS a
            LEFT JOIN comarca_population AS p
            USING (comarca_id, year)
          ),
            filled_population AS (
            SELECT
              comarca_id,
              year,
              LAST_VALUE(population IGNORE NULLS)
                OVER (PARTITION BY comarca_id ORDER BY year ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
                AS population,
              LAST_VALUE(population_ge65 IGNORE NULLS)
                OVER (PARTITION BY comarca_id ORDER BY year ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
                AS population_ge65
            FROM joined_population
          ),
            social_services_residence as (select * from social_services where service_type_id='RES-003'),
            joined_social_services AS (
            SELECT
              a.comarca_id,
              a.year,
              ss.total_capacit
            FROM all_combinations AS a
            LEFT JOIN social_services_residence AS ss
            USING (comarca_id, year)
          ),
            filled_social_services AS (
            SELECT
              comarca_id,
              year,
              SUM(total_capacit)
                OVER (
                  PARTITION BY comarca_id
                  ORDER BY year
                  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) AS total_capacit
            FROM joined_social_services
          ),
            clean_filled_social_services AS (select * from filled_social_services where total_capacit is NOT NULL),
          complete_data as (
            select * from
            filled_population as p
            JOIN clean_filled_social_services as ss
            USING (comarca_id, year)
          ),
            with_coverage as (
            select comarca_id, year, total_capacit*100.0 / population_ge65 as coverage_ratio, total_capacit, population_ge65 from complete_data
            )
          select comarca_id, CAST(year as INT) as year, ROUND(coverage_ratio, 2) as coverage_ratio from with_coverage order by comarca_id, year;`);

const zip = new JSZip();

const social_services_empty_last_year = await conn.runAndReadAll("SELECT *  FROM social_services_empty_last_year");
zip.file("social_services_empty_last_year.json", JSON.stringify(social_services_empty_last_year.getRowObjectsJson()));
const municipal_coverage = await conn.runAndReadAll("SELECT *  FROM municipal_coverage");
zip.file("municipal_coverage.json", JSON.stringify(municipal_coverage.getRowObjectsJson()));
const comarca_population = await conn.runAndReadAll("SELECT *  FROM comarca_population");
zip.file("comarca_population.json", JSON.stringify(comarca_population.getRowObjectsJson()));
const comarca_coverage = await conn.runAndReadAll("SELECT *  FROM comarca_coverage");
zip.file("comarca_coverage.json", JSON.stringify(comarca_coverage.getRowObjectsJson()));
const municipal = await conn.runAndReadAll("SELECT *  FROM municipal");
zip.file("municipal.json", JSON.stringify(municipal.getRowObjectsJson()));


zip
  .generateNodeStream({ type: "nodebuffer", streamFiles: true })
  .pipe(process.stdout);
