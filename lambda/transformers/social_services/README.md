# Social Services Data Transformer Lambda

This Rust Lambda function transforms raw social services data from the Catalunya Open Data API into clean, validated, and enriched parquet files ready for analytics.

## Overview

The transformer processes social services data from the landing S3 bucket, enriches it with catalog data, performs fuzzy matching on municipality names, deduplicates records, and outputs cleaned data to the staging layer.

## Functionality

### 1. Catalog Data Loading
Loads three catalog parquet files from the catalog S3 bucket:
- **municipals**: Municipality information with comarca (county) mappings
- **service_type**: Service type classifications and descriptions (e.g., "RES-002" = "Servei de llar residència per a gent gran")
- **service_qualification**: Service qualification types (public/private/other)

### 2. Data Validation
Validates that all values in source data exist in catalogs:
- Service types must have matching descriptions in service_type catalog
- Service qualifications must have matching descriptions in service_qualification catalog (nulls allowed)

Fails transformation if any unmapped values are found.

### 3. Data Cleaning
- Replaces "null" string values with actual nulls in `qualificacio` field
- Standardizes comarca names: "Val d'Aran" → "Aran"
- Handles nullable service qualification values

### 4. Catalog Enrichment
Performs left joins to add normalized IDs:
- Maps service type descriptions to `service_type_id`
- Maps service qualification descriptions to `service_qualification_id`
- Maps comarca names to `municipal_id` and `comarca_id`

### 5. Municipality Name Fuzzy Matching
When municipality names don't exactly match between source data and catalog:

1. **Normalizes text**: Removes accents, special characters, converts to lowercase
   - e.g., "Sant Joan de Vilatorrada" → "sant joan de vilatorrada"

2. **Tokenizes**: Splits into words (filters single chars)
   - e.g., ["sant", "joan", "vilatorrada"]

3. **Calculates similarity**: Intersection of token sets
   - Higher similarity score = better match

4. **Deduplicates**: Keeps records with highest similarity score for each `registre`

### 6. Data Transformations
- **Date conversion**: `inscripcio` string → `inscription_date` date (YYYY-MM-DD)
- **Integer casting**: `capacitat` → `capacity` (Int32)
- **Column renaming**:
  - `registre` → `social_service_register_id`
  - Adds `downloaded_date` from payload

### 7. Data Integrity Validation
Ensures unique register IDs are preserved through transformation:
- Compares original vs final unique count of `registre`
- Fails if records were lost during transformation

### 8. Glue Partition Creation (Non-Local)
When not running in local environment:
- Creates Glue partition for `social_services` table
- Partition key: `downloaded_date` = YYYYMMDD
- Checks if partition exists before creation

## Environment Variables

- `BUCKET_NAME` (required): S3 bucket name for data operations
- `CATALOG_BUCKET_NAME` (required): S3 bucket name containing catalog parquet files
- `AWS_ENDPOINT_URL` (optional): Custom S3 endpoint for LocalStack

## Input

```json
{
  "environment": "local|dev|prod",
  "downloaded_date": "20240101",
  "bucket_name": "catalunya-data-dev",
  "athena_database_name": "catalunya_data_dev",
  "semantic_identifier": "social_services"
}
```

## Output

Success response:
```json
{
  "statusCode": 200,
  "success": true,
  "message": "Successfully processed files for date 20240101",
  "timestamp": "2024-01-01T12:00:00Z",
  "processor": "social-services-transformer",
  "data": {
    "source_prefix": "landing/social_services/downloaded_date=20240101/",
    "target_key": "staging/social_services/downloaded_date=20240101/social_services.parquet",
    "status": "success",
    "files_processed": 5,
    "raw_records": 5000,
    "clean_records": 4950,
    "target_location": "s3://catalunya-data-dev/staging/social_services/downloaded_date=20240101/social_services.parquet"
  }
}
```

Error response:
```json
{
  "statusCode": 500,
  "success": false,
  "message": "Validation failed with 3 errors",
  "timestamp": "2024-01-01T12:00:00Z",
  "processor": "social-services-transformer",
  "data": null
}
```

## Processing Steps

1. Download JSON files from `s3://{bucket}/landing/{semantic_identifier}/downloaded_date={date}/`
2. Filter for files matching pattern: `/\d{8}\.json$` (e.g., `00000000.json`)
3. Load each JSON file into Polars DataFrame
4. Select required columns: `registre, tipologia, inscripcio, capacitat, municipi, comarca, qualificacio`
5. Apply data cleaning transformations
6. Join with catalogs to add IDs
7. Normalize and fuzzy match municipality names
8. Sort by `tokens_similar` (descending) and deduplicate on key fields
9. Apply final type conversions
10. Upload merged parquet to `s3://{bucket}/staging/{semantic_identifier}/downloaded_date={date}/{semantic_identifier}.parquet`
11. Create Glue partition (if not local)

## Error Handling

The Lambda includes specific error handling for:
- **Catalog file not found**: Required catalog parquet files missing from S3
- **Unmapped service types**: Service type in data but not in catalog
- **Unmapped qualifications**: Service qualification in data but not in catalog (nulls allowed)
- **No data files**: No matching JSON files found in source prefix
- **Data integrity failure**: Record count mismatch before/after transformation
- **Glue partition creation failure**: AWS Glue API errors
- **S3 upload failure**: AWS S3 API errors

## Dependencies

- `polars`: DataFrame processing and lazy evaluation
- `aws-sdk-s3`: S3 client for data operations
- `aws-sdk-glue`: Glue client for partition management
- `regex`: Pattern matching for file filtering
- `chrono`: Date/time handling
- `serde`: JSON serialization/deserialization

## Build & Test

```bash
# Build for production
cargo lambda build --release --target x86_64-unknown-linux-gnu

# Run unit tests
cargo test

# Local testing (requires LocalStack)
cargo lambda watch
cargo lambda invoke --data-ascii '{"environment":"local","downloaded_date":"20240101","bucket_name":"catalunya-data-dev","athena_database_name":"catalunya_data_dev","semantic_identifier":"social_services"}' --remote -p localstack --endpoint-url http://localhost:4566
```

## File Naming Conventions

- **Source JSONs**: `{offset:08d}.json` (e.g., `00000000.json`)
- **Target Parquet**: `{semantic_identifier}.parquet` (e.g., `social_services.parquet`)
- **S3 keys**:
  - Source: `landing/{semantic_identifier}/downloaded_date={YYYYMMDD}/{offset:08d}.json`
  - Target: `staging/{semantic_identifier}/downloaded_date={YYYYMMDD}/{semantic_identifier}.parquet`
