# dbt Local Development Guide

How to develop, run, and debug dbt models locally against MiniStack.

## Architecture

| Layer             | Local                                                              | Prod                                |
| ----------------- | ------------------------------------------------------------------ | ----------------------------------- |
| dbt adapter       | `dbt-duckdb` (target `local`)                                      | `dbt-athena` (targets `dev`/`prod`) |
| Storage           | MiniStack S3 (persisted in `cloudgentgran-ministack-state` volume) | Real S3                             |
| Catalog           | MiniStack Glue (created by `post-deploy-ministack.sh`)             | Real Glue                           |
| Queries/notebooks | MiniStack Athena (read-only, DuckDB engine)                        | Real Athena                         |

Model config is adapter-aware (`macros/adapter_aware_table_config.sql`):

- **duckdb**: `materialized='external'`, parquet written to `s3://$DATA_BUCKET/marts/<model>` via httpfs
- **athena**: `materialized='table'` (CTAS)

## Prerequisites

```bash
scripts/start-local-dev.sh full-deploy   # fresh state + CDK deploy + Glue/Athena resources
scripts/start-local-dev.sh start         # subsequent starts (preserves state)
```

Required Airflow keys live in `.env` (`AIRFLOW_FERNET_KEY`, `AIRFLOW_SECRET_KEY`) — the start script refuses to run without them.

AWS CLI access to MiniStack:

```bash
aws --profile localstack <cmd>   # profile has endpoint_url=http://localhost:4566 baked in
```

## Running dbt manually

Everything runs inside the Airflow container (`/opt/airflow/dbt` is a live mount of `./dbt` — edits on the host are immediate, no restart):

```bash
# Run one model
docker exec -e DBT_TARGET=local cloudgentgran-airflow \
  bash -c "cd /opt/airflow/dbt/mart && dbt run --select comarca_population"

# Run one test
docker exec -e DBT_TARGET=local cloudgentgran-airflow \
  bash -c "cd /opt/airflow/dbt/mart && dbt test --select comarca_population"

# Run a single named test
docker exec -e DBT_TARGET=local cloudgentgran-airflow \
  bash -c "cd /opt/airflow/dbt/mart && dbt test --select not_null_municipal_coverage_population_age_65_and_over"

# Ad-hoc query against compiled models/sources
docker exec -e DBT_TARGET=local cloudgentgran-airflow \
  bash -c "cd /opt/airflow/dbt/mart && dbt show --inline \"select * from {{ ref('municipal_coverage') }} limit 10\""
```

## Overwrite / re-run behavior

- `overwrite_or_ignore: true` in the model config → repeated `dbt run` overwrites same-named files. No manual cleanup needed for normal iterations.
- Stale extra files (a previous run wrote more `data_N.parquet` parts than the current one) are only removed by:
  - the DAG: `DbtAthenaOperator._cleanup_mart_directory()` deletes `s3://$DATA_BUCKET/marts/<model>/` before every local run, or
  - manually: `aws --profile localstack s3 rm s3://catalunya-data-dev/marts/<model>/ --recursive`

## Debugging a failing test

Example: `not_null_municipal_coverage_population_age_65_and_over`.

1. **Reproduce** with the single-test command above.
2. **Inspect the model output** — rows violating the test:
   ```bash
   docker exec -e DBT_TARGET=local cloudgentgran-airflow \
     bash -c "cd /opt/airflow/dbt/mart && dbt show --inline \"select * from {{ ref('municipal_coverage') }} where population_age_65_and_over is null limit 20\""
   ```
3. **Inspect inputs** — sources read from MiniStack S3 (`read_staging_data`, `read_catalog_data` macros) or directly:
   ```bash
   aws --profile localstack s3 ls s3://catalunya-data-dev --recursive
   ```
4. **Query via MiniStack Athena** (prod-identical API, reads Glue catalog):
   ```bash
   QID=$(aws --profile localstack athena start-query-execution \
     --query-string "SELECT * FROM catalunya_data_dev.municipal_population WHERE year = 2025 LIMIT 10" \
     --query-execution-context Database=catalunya_data_dev \
     --work-group catalunya-workgroup-dev \
     --result-configuration OutputLocation=s3://catalunya-athena-results-dev/query-results/ \
     --query QueryExecutionId --output text)
   sleep 2
   aws --profile localstack athena get-query-results --query-execution-id "$QID"
   ```
   Direct parquet read also works: `SELECT ... FROM read_parquet('s3://bucket/marts/model/*.parquet')`.
5. **Fix + iterate**: edit the model/test in `dbt/mart/` on the host, re-run. No container restart.
6. **Confirm in Airflow**: re-run the DAG task from the UI.

Common causes for NULLs in coverage models:

- upstream extractor wrote new keys but the transformer/mart lambdas were not re-run → stale `marts/municipal_population`
- municipalities present in services data but missing in population data (join semantics)
- landing data partially deleted by a manual `s3 rm`

## MiniStack Athena limitations (why dbt still uses duckdb locally)

- Each query executes in a fresh in-memory DuckDB (`:memory:`) — **no persistence**
- DDL (`CREATE`/`DROP`/`ALTER`) returns mock success — **no CTAS materialization**
- Glue tables resolve read-only via `classification` table parameter (must be `parquet`; set by `post-deploy-ministack.sh`)

So: duckdb writes the models, Athena verifies them. If MiniStack adds persistent writes, `dbt-athena` can replace the duckdb target.

## Troubleshooting

| Symptom                                           | Cause                                       | Fix                                                              |
| ------------------------------------------------- | ------------------------------------------- | ---------------------------------------------------------------- |
| `Could not establish connection ... HTTP GET`     | stale `endpoint` in `dbt/profiles.yml`      | regenerate: `cp dbt/mart/profiles_template.yml dbt/profiles.yml` |
| `ERROR creating sql external model` on 2nd run    | pre-`overwrite_or_ignore` config            | update macro, or `s3 rm` the model prefix                        |
| Athena: `No files found that match ... *.csv`     | Glue table missing `classification=parquet` | re-run `infrastructure/post-deploy-ministack.sh`                 |
| `Checksum algorithm not supported` on `aws s3 cp` | aws-cli defaults to CRC64NVME               | add `--checksum-algorithm SHA256`                                |
| `ReadTimeoutError` on Lambda invoke               | boto3 default 60s read timeout              | all `LambdaInvokeFunctionOperator` set `botocore_config` 900s    |
| lambda `service error` / `dispatch failure`       | stale deploy without `AWS_ENDPOINT_URL`     | re-run `infrastructure/deploy-localstack.sh`                     |
