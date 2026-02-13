# Population Municipal Greater 65 Mart Lambda

This Rust Lambda function moves the processed population data from the staging layer to the marts layer for analytics consumption.

## Overview

The mart lambda performs a simple S3 copy operation to make the transformed population data available in the marts layer for dbt models and analytics.

## Functionality

The mart lambda:
1. **Receives source prefix** indicating the staging location
2. **Constructs target key** for the marts layer
3. **Copies the parquet file** directly from staging to marts via S3 CopyObject
4. **Returns success/failure status**

### S3 Copy Operation

Uses AWS S3 `CopyObject` API:
- Source: `s3://{bucket}/{source_prefix}`
- Target: `s3://{bucket}/{target_key}`
- No data transformation or processing
- Efficient: Server-side copy without downloading data

## Environment Variables

- `BUCKET_NAME` (required): S3 bucket name for data operations
- `SEMANTIC_IDENTIFIER` (required): Semantic identifier (typically "municipal_population")
- `AWS_ENDPOINT_URL` (optional): Custom S3 endpoint for LocalStack

## Input

```json
{
  "source_prefix": "staging/population_municipal_greater_65/population_municipal_greater_65.parquet"
}
```

## Output

Success response:
```json
{
  "status": "succeeded",
  "target_prefix": "marts/municipal_population/municipal_population.parquet"
}
```

Failure response:
```json
{
  "status": "failed",
  "target_prefix": null
}
```

## Processing Steps

1. Construct source path: `s3://{bucket_name}/{source_prefix}`
2. Construct target key: `marts/{semantic_identifier}/{semantic_identifier}.parquet`
3. Execute S3 CopyObject API call
4. Return status and target location

## Error Handling

The Lambda includes specific error handling for:
- **Missing environment variables**: BUCKET_NAME or SEMANTIC_IDENTIFIER not set
- **S3 copy failure**: AWS S3 API errors during copy operation
- **Source not found**: Staging file doesn't exist

## Dependencies

- `aws-sdk-s3`: S3 client for copy operations
- `anyhow`: Error handling

## Build & Test

```bash
# Build for production
cargo lambda build --release --target x86_64-unknown-linux-gnu

# Run unit tests
cargo test

# Local testing (requires LocalStack)
cargo lambda watch
cargo lambda invoke --data-ascii '{"source_prefix":"staging/population_municipal_greater_65/population_municipal_greater_65.parquet"}' --remote -p localstack --endpoint-url http://localhost:4566 population_municipal_greater_65_mart
```

## File Naming Conventions

- **Source Parquet**: `{semantic_identifier}.parquet` in staging
- **Target Parquet**: `{semantic_identifier}.parquet` in marts
- **S3 keys**:
  - Source: `staging/{semantic_identifier}/{semantic_identifier}.parquet`
  - Target: `marts/{semantic_identifier}/{semantic_identifier}.parquet`

## Usage in Pipeline

This lambda is invoked by Airflow as the final step in the population data pipeline:

```
Extractor → Transformer → Mart → dbt models
```

The output parquet file is used by dbt models in `dbt/mart/models/marts/` to create:
- `comarca_population.sql`: Aggregated population by comarca
- `municipal_coverage.sql`: Coverage metrics by municipality
