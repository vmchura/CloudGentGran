# Social Services API Extractor Lambda

This Lambda function extracts social services data from the Catalunya Open Data API and uploads it to S3.

## Overview

The social services extractor fetches data from the [Catalunya Open Data portal](https://analisi.transparenciacatalunya.cat/Societat-benestar/Registre-d-entitats-serveis-i-establiments-socials/ivft-vegh/about_data) in batches and stores it in the landing S3 bucket for further processing.

**Dataset**: Registre d'entitats, serveis i establiments socials (serveis socials bàsics i especialitzats)  
**Dataset Identifier**: ivft-vegh  
**Description**: Registry of all social services (basic and specialized) from public and private entities

## Functionality

- Fetches data from the Catalunya social services API in batches of 1000 records
- Handles pagination using offset parameters
- Uploads each batch as a separate JSON file to S3
- Returns metadata for Airflow orchestration

## Environment Variables

- `BUCKET_NAME` (required): Name of the S3 landing bucket
- `DATASET_IDENTIFIER` (required): API dataset identifier (e.g., ivft-vegh)
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
  "message": "Successfully processed 5 blocks with 5000 total records",
  "timestamp": "2024-01-01T00:00:00",
  "extractor": "social-services-api-extractor",
  "data": {
    "bucket": "landing-bucket",
    "semantic_identifier": "social-services",
    "downloaded_date": "20240101",
    "file_count": 5,
    "total_records": 5000,
    "s3_keys": ["landing/social-services/downloaded_date=20240101/00000000.json", ...],
    "source_prefix": "landing/social-services/downloaded_date=20240101/",
    "extraction_completed_at": "2024-01-01T00:00:00",
    "next_step": "trigger_transformer",
    "transformer_payload": {...}
  }
}
```

## Error Handling

The Lambda includes specific error handling for:
- **ConfigurationError**: Missing required environment variables
- **APIError**: HTTP errors, URL errors, timeouts when fetching data
- **DataValidationError**: Invalid JSON responses, unexpected data format
- **S3OperationError**: S3 upload failures
- **AWS Service Errors**: ClientError, NoCredentialsError, EndpointConnectionError

Error responses include:
- `statusCode`: HTTP status code (400, 500, 503)
- `success`: false
- `message`: Human-readable error message
- `data.error_type`: Specific exception type

## Testing

Run tests with pytest:
```bash
python -m pytest test_api_extractor.py -v
```

Tests cover:
- Successful lambda execution with data extraction
- No data available scenario
- S3 upload functionality
- Response creation
- S3 client configuration

## API Details

The Lambda fetches data from:
```
https://analisi.transparenciacatalunya.cat/resource/{DATASET_IDENTIFIER}.json?$offset={offset}
```

Data is fetched in batches of 1000 records until no more data is available.
