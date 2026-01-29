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
  const useLocalStack = process.env.AWS_ENDPOINT_URL?.includes('localstack') || process.env.AWS_ENDPOINT_URL?.includes('4566');

  if (useLocalStack) {
    console.error("Using LocalStack credentials from environment");
    await conn.run(`
      CREATE OR REPLACE SECRET aws_s3 (
        TYPE S3,
        KEY_ID '${process.env.AWS_ACCESS_KEY_ID}',
        SECRET '${process.env.AWS_SECRET_ACCESS_KEY}',
        REGION 'eu-west-1',
        ENDPOINT '${process.env.AWS_ENDPOINT_URL?.replace('http://', '')}',
        URL_STYLE 'path',
        USE_SSL false
      );
    `);
  } else {
    console.error("Using AWS credentials from environment");
    await conn.run(`
      CREATE OR REPLACE SECRET aws_s3 (
        TYPE S3,
        KEY_ID '${process.env.AWS_ACCESS_KEY_ID}',
        SECRET '${process.env.AWS_SECRET_ACCESS_KEY}',
        ${process.env.AWS_SESSION_TOKEN ? `SESSION_TOKEN '${process.env.AWS_SESSION_TOKEN}',` : ''}
        REGION 'eu-west-1'
      );
    `);
  }
}

// Load data
await conn.run(`
    CREATE TABLE population AS
    SELECT * FROM read_parquet('s3://${BUCKET_DATA}/marts/municipal_population/municipal_population.parquet');

    CREATE TABLE municipal AS
    SELECT * FROM read_parquet('s3://${BUCKET_CATALOG}/municipals/*');

    CREATE TABLE social_services AS
    SELECT * FROM read_parquet('s3://${BUCKET_DATA}/marts/social_services_by_service_municipal/*');

    CREATE TABLE service_qualification AS
    SELECT * FROM read_parquet('s3://${BUCKET_CATALOG}/service_qualification/*');

    CREATE TABLE service_type AS
    SELECT * FROM read_parquet('s3://${BUCKET_CATALOG}/service_type/*');

    CREATE TABLE comarca_population AS
    SELECT * FROM read_parquet('s3://${BUCKET_DATA}/marts/comarca_population/*');

    CREATE TABLE municipal_coverage AS
    SELECT * FROM read_parquet('s3://${BUCKET_DATA}/marts/municipal_coverage/*');

    CREATE TABLE comarca_coverage AS
    SELECT * FROM read_parquet('s3://${BUCKET_DATA}/marts/comarca_coverage/*');
`);

console.error(`Processing: social_services_empty_last_year`);
await conn.run(`CREATE TABLE social_services_empty_last_year as 
      WITH municipals AS (
        SELECT DISTINCT municipal_id, comarca_id
        FROM municipal
      ),
      social_service_types AS (
        SELECT DISTINCT service_type_id
        FROM social_services
      ),
      service_qualification_types AS (
        SELECT DISTINCT service_qualification_id
        FROM social_services
      ),
      relevant_combinations AS (
        SELECT DISTINCT
          municipal_id,
          service_type_id,
          service_qualification_id
        FROM social_services
        WHERE total_capacit > 0
      ),
      all_combinations AS (
        SELECT 
          rc.municipal_id,
          rc.service_type_id,
          rc.service_qualification_id,
          m.comarca_id,
          y.year AS year
        FROM relevant_combinations rc
        JOIN municipals m USING (municipal_id)
        CROSS JOIN generate_series(1975, 2026) AS y(year)
      ),
      joined AS (
        SELECT
          municipal_id,
          service_type_id,
          service_qualification_id,
          ac.comarca_id,
          year,
          COALESCE(ss.total_capacit, 0) AS total_capacit
        FROM all_combinations ac
        LEFT JOIN social_services ss
          USING (municipal_id, service_type_id, service_qualification_id, year)
      ),
      first_nonzero AS (
        SELECT
          municipal_id,
          service_type_id,
          service_qualification_id,
          MIN(year) AS first_year
        FROM joined
        WHERE total_capacit > 0
        GROUP BY municipal_id,service_type_id,service_qualification_id
      )
      SELECT
        municipal_id,
        service_type_id,
        service_qualification_id,
        j.comarca_id,
        CAST(j.year AS INT) AS year,
        CAST(j.total_capacit AS INT) AS total_capacit
      FROM joined j
      JOIN first_nonzero f
        USING (municipal_id, service_type_id, service_qualification_id)
      WHERE j.year >= f.first_year
      ORDER BY year, comarca_id, municipal_id, service_type_id;`);


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
const service_type = await conn.runAndReadAll("SELECT *  FROM service_type");
zip.file("service_type.json", JSON.stringify(service_type.getRowObjectsJson()));
const service_qualification = await conn.runAndReadAll("SELECT *  FROM service_qualification");
zip.file("service_qualification.json", JSON.stringify(service_qualification.getRowObjectsJson()));
const population = await conn.runAndReadAll("SELECT municipal_id, CAST(population_age_65_and_over AS INT) as population_age_65_and_over, CAST(population AS INT) as population, CAST(year AS INT) as year  FROM population");
zip.file("population.json", JSON.stringify(population.getRowObjectsJson()));

zip
  .generateNodeStream({ type: "nodebuffer", streamFiles: true })
  .pipe(process.stdout);
