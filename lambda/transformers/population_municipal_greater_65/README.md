# Population Municipal Greater 65 Transformer Lambda

This Rust Lambda function processes raw population data from the IDESCAT API (aged 65 and over by municipality) and transforms it into parquet format for the staging layer.

## Overview

The transformer reads JSON files from the landing S3 bucket containing population census data, parses the complex nested IDESCAT API structure, extracts relevant population metrics, and outputs a clean parquet file to staging.

## Functionality

### 1. IDESCAT API Structure Parsing
The IDESCAT API returns data in a complex nested format:

```json
{
  "dimension": {
    "YEAR": {
      "category": {
        "index": ["2022"]
      }
    },
    "MUN": {
      "category": {
        "index": ["010001", "010002", ...]
      }
    }
  },
  "size": [1000, 2],  // Matrix dimensions
  "value": [100, 2000, 150, 2100, ...]  // Interleaved values
}
```

The transformer:
- Calculates matrix dimensions from `size` array: `total_items / 2 - 1`
- Extracts year from `dimension.YEAR.category.index` (expects single year)
- Extracts municipal codes from `dimension.MUN.category.index`
- Parses interleaved `value` array where even indices = population aged 65+, odd indices = total population

### 2. Data Extraction Logic
Given the interleaved value pattern `[age65_m1, total_m1, age65_m2, total_m2, ...]`:

- **Age 65+ values**: Extract at even indices (0, 2, 4, ...)
- **Total population values**: Extract at odd indices (1, 3, 5, ...)
- **Skip last value**: API includes a trailing summary value that's excluded

### 3. File Filtering
Only processes files matching pattern `/\d{4}\.json$`:
- Example matches: `2022.json`, `2021.json`
- Ignores: `metadata.json`, `00000000.json`, etc.

### 4. Data Validation
- Ensures exactly 1 year in the index (single-year datasets)
- Validates all municipal codes are strings
- Validates population values are numeric (f64)
- Fails transformation if no files match the pattern

### 5. Output Schema
Creates parquet with columns:
- `municipal_id`: Municipal code (string, e.g., "010001")
- `population_age_65_and_over`: Population aged 65 and over (int64)
- `population`: Total population (int64)
- `year`: Census year (int64, repeated for all rows)

## Environment Variables

- `BUCKET_NAME` (required): S3 bucket name for data operations
- `SEMANTIC_IDENTIFIER` (required): Semantic identifier (typically "population_municipal_greater_65")
- `AWS_ENDPOINT_URL` (optional): Custom S3 endpoint for LocalStack

## Input

```json
{
  "source_prefix": "landing/population_municipal_greater_65/"
}
```

## Output

Success response:
```json
{
  "status": "succeeded",
  "target_prefix": "staging/population_municipal_greater_65/population_municipal_greater_65.parquet"
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

1. List objects in S3 with prefix from input
2. Filter JSON files matching `/\d{4}\.json$` pattern
3. For each file:
   - Download and parse JSON
   - Calculate matrix dimensions from `size` array
   - Extract single year from `YEAR` index
   - Parse interleaved `value` array into two series (65+, total)
   - Create DataFrame with 4 columns
   - Add to collection for merging
4. Vertically concatenate all DataFrames
5. Upload merged parquet to S3

## Error Handling

The Lambda includes specific error handling for:
- **No matching files**: Returns status "failed" when no JSON files match pattern
- **Invalid JSON structure**: Malformed IDESCAT API response
- **Wrong year count**: Expects exactly 1 year in index
- **Missing fields**: Required fields absent from JSON structure
- **Numeric parsing errors**: Population values not valid numbers
- **S3 upload failure**: AWS S3 API errors

## Dependencies

- `polars`: DataFrame processing and vertical concatenation
- `aws-sdk-s3`: S3 client for data operations
- `regex`: Pattern matching for file filtering
- `serde_json`: JSON parsing
- `anyhow`: Error handling

## Build & Test

```bash
# Build for production
cargo lambda build --release --target x86_64-unknown-linux-gnu

# Run unit tests
cargo test

# Local testing (requires LocalStack)
cargo lambda watch
cargo lambda invoke --data-ascii '{"source_prefix":"landing/population_municipal_greater_65/"}' --remote -p localstack --endpoint-url http://localhost:4566 population_municipal_greater_65
```

## File Naming Conventions

- **Source JSONs**: `{year}.json` (e.g., `2022.json`)
- **Target Parquet**: `{semantic_identifier}.parquet`
- **S3 keys**:
  - Source: `landing/{semantic_identifier}/{year}.json`
  - Target: `staging/{semantic_identifier}/{semantic_identifier}.parquet`
