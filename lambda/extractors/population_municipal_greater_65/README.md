# Population Municipal Greater 65 API Extractor Lambda

This Lambda function extracts population data for people aged 65 and over by municipality from the IDESCAT API and uploads it to S3.

## Overview

The population extractor fetches demographic data from the [IDESCAT API](https://api.idescat.cat/) for people aged 65 and over at the municipal level. It processes data for all available years and stores it in the landing S3 bucket.

## Functionality

- Discovers the API endpoint by navigating through IDESCAT API hierarchy
- Fetches population data for each available year
- Implements retry logic with exponential backoff for failed requests
- Uploads each year's data as a separate JSON file to S3

## Environment Variables

- `BUCKET_NAME` (required): Name of the S3 landing bucket
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
  "message": "Successfully processed 10 blocks",
  "timestamp": "2024-01-01T00:00:00",
  "extractor": "population-municipal-greater-65-api-extractor",
  "data": {
    "bucket": "landing-bucket",
    "semantic_identifier": "population-municipal-gt-65",
    "extraction_completed_at": "2024-01-01T00:00:00"
  }
}
```

## Error Handling

The Lambda includes specific error handling for:
- **ConfigurationError**: Missing required environment variables
- **APIError**: HTTP errors, URL errors, timeouts when fetching data
- **DataValidationError**: Invalid JSON responses, unexpected data structure, incomplete downloads
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
- Successful lambda execution
- S3 upload functionality
- Response creation
- S3 client configuration
- Base URL fetching

## API Details

The Lambda navigates through the IDESCAT API:
1. Fetches available statistics from `https://api.idescat.cat/taules/v2`
2. Finds "Cens de població i habitatges"
3. Navigates to "Població. Per sexe i edat en grans grups"
4. Selects "Per municipis" territory level
5. Fetches data for each available year

Data is fetched with retry logic (3 attempts with exponential backoff).
