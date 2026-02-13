# Service Type Initializer Lambda

This Lambda function initializes the service type catalog by creating a Parquet file from predefined service type data and uploading it to S3.

## Overview

The service type initializer creates a catalog of social service types used in the Catalunya social services data pipeline. It generates a Parquet file containing service type definitions and uploads it to the catalog bucket.

## Functionality

- Reads predefined service type data (59 service types)
- Creates a Parquet file from the data
- Uploads the file to S3 with metadata
- Returns execution status and S3 location

## Environment Variables

- `CATALOG_BUCKET_NAME` (required): Name of the S3 bucket for catalog data
- `ENVIRONMENT` (optional): Environment name (default: 'dev')

## Input

The Lambda expects an event with:
```json
{
  "table_name": "service_type"
}
```

## Output

Success response:
```json
{
  "statusCode": 200,
  "body": {
    "message": "Parquet file created successfully for table service_type",
    "table_name": "service_type",
    "record_count": 66,
    "s3_location": "s3://bucket/service_type/service_type.parquet",
    "s3_key": "service_type/service_type.parquet",
    "columns": ["service_type_id", "service_type_description", "created_at"],
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
python -m pytest test_service_type_initializer.py -v
```

Tests cover:
- Successful lambda execution
- Missing table_name parameter
- Parquet file creation
- Empty data handling
- S3 upload functionality
