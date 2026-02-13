# Service Qualification Initializer Lambda

This Lambda function initializes the service qualification catalog by creating a Parquet file from predefined service qualification data and uploading it to S3.

## Overview

The service qualification initializer creates a catalog of service qualifications used in the Catalunya social services data pipeline. It generates a Parquet file containing qualification definitions (public, private, etc.) and uploads it to the catalog bucket.

## Functionality

- Reads predefined service qualification data (3 qualifications)
- Creates a Parquet file from the data
- Uploads the file to S3 with metadata
- Returns execution status and S3 location

## Environment Variables

- `CATALOG_BUCKET_NAME` (required): Name of the S3 bucket for catalog data

## Input

The Lambda expects an event with:
```json
{
  "table_name": "service_qualification"
}
```

## Output

Success response:
```json
{
  "statusCode": 200,
  "body": {
    "message": "Parquet file created successfully for table service_qualification",
    "table_name": "service_qualification",
    "record_count": 3,
    "s3_location": "s3://bucket/service_qualification/service_qualification.parquet",
    "s3_key": "service_qualification/service_qualification.parquet",
    "columns": ["service_qualification_id", "service_qualification_description", "created_at"],
    "created_at": "2024-01-01T00:00:00"
  }
}
```

## Error Handling

The Lambda includes specific error handling for:
- **ConfigurationError**: Missing required environment variables
- **S3OperationError**: S3 upload failures
- **DataProcessingError**: Data validation and processing errors
- **AWS Service Errors**: ClientError, NoCredentialsError, EndpointConnectionError

Error responses include:
- `statusCode`: HTTP status code (400, 422, 500, 503)
- `error`: Error category
- `message`: Human-readable error message
- `error_type`: Specific exception type

## Testing

Run tests with pytest:
```bash
python -m pytest test_service_qualification_initializer.py -v
```

Tests cover:
- Successful lambda execution
- Missing table_name parameter
- Parquet file creation
- Empty data handling
- S3 upload functionality
