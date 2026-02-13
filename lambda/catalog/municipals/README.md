# Municipals Initializer Lambda

This Lambda function extracts municipal data from the Catalunya Open Data API and creates a Parquet file in the catalog S3 bucket.

## Overview

The municipals initializer fetches data about municipalities in Catalunya from the Open Data portal, processes it into a clean DataFrame with standardized column names, and uploads it as a Parquet file to the catalog bucket.

## Functionality

- Fetches municipal data from the Catalunya Open Data API in batches
- Processes and transforms the data (renames columns, filters fields)
- Creates a Parquet file from the processed data
- Uploads the file to S3 with metadata
- Returns metadata for Airflow orchestration

## Environment Variables

- `CATALOG_BUCKET_NAME` (required): Name of the S3 catalog bucket
- `DATASET_IDENTIFIER` (required): API dataset identifier
- `SEMANTIC_IDENTIFIER` (required): Semantic identifier for the dataset
- `AWS_ENDPOINT_URL` (optional): Custom S3 endpoint URL for LocalStack

## Input

The Lambda can be triggered with an empty event:
```json
{}
```

## Output

Success response:
```json
{
  "statusCode": 200,
  "success": true,
  "message": "Successfully processed 947 records",
  "timestamp": "2024-01-01T00:00:00",
  "extractor": "social-services-api-extractor",
  "data": {
    "bucket": "catalog-bucket",
    "semantic_identifier": "municipals",
    "downloaded_date": "20240101",
    "total_records": 947,
    "s3_key": "municipals/municipals.parquet",
    "extraction_completed_at": "2024-01-01T00:00:00",
    "next_step": "trigger_transformer",
    "transformer_payload": {...}
  }
}
```

## Data Processing

The Lambda performs the following data transformations:
- Maps `codi` → `municipal_id`
- Maps `nom` → `municipal_name`
- Maps `codi_comarca` → `comarca_id`
- Maps `nom_comarca` → `comarca_name`

## Error Handling

The Lambda includes specific error handling for:
- **ConfigurationError**: Missing required environment variables
- **APIError**: HTTP errors, URL errors, timeouts when fetching data
- **DataValidationError**: Invalid JSON responses, unexpected data format, no data extracted
- **DataProcessingError**: Data transformation errors, empty data
- **S3OperationError**: S3 upload failures
- **AWS Service Errors**: ClientError, NoCredentialsError, EndpointConnectionError

Error responses include:
- `statusCode`: HTTP status code (400, 422, 500, 503)
- `success`: false
- `message`: Human-readable error message
- `data.error_type`: Specific exception type

## Testing

Run tests with pytest:
```bash
python -m pytest test_municipals_initializer.py -v
```

Tests cover:
- Successful lambda execution
- Data processing with complete columns
- Data processing with partial columns
- Data processing with no expected columns
- Empty data handling
- S3 upload functionality
- Response creation
- S3 client configuration

## API Details

The Lambda fetches data from:
```
https://analisi.transparenciacatalunya.cat/resource/{DATASET_IDENTIFIER}.json?$offset={offset}
```

Data is fetched in batches of 1000 records until no more data is available.
