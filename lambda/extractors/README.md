# Catalunya Data Pipeline - Lambda Extractors

This directory contains Lambda functions for extracting data from various sources and writing to the landing layer of our data lake.

## API Extractor

The `api-extractor.py` function extracts data from public APIs and stores it in the S3 landing bucket.

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `BUCKET_NAME` | S3 bucket for data storage | `catalunya-data-dev` |
| `API_URL` | URL of the API to extract from | `https://jsonplaceholder.typicode.com/posts` |
| `API_NAME` | Name identifier for the API | `jsonplaceholder` |
| `ENVIRONMENT` | Environment name | `dev` or `prod` |
| `REGION` | AWS region | `eu-west-1` |

### S3 Output Structure

Data is stored in the following partitioned structure:

```
s3://bucket-name/landing/{api_name}/year={YYYY}/month={MM}/day={DD}/{api_name}_{timestamp}.json
```

Example:
```
s3://catalunya-data-dev/landing/jsonplaceholder/year=2025/month=08/day=08/jsonplaceholder_20250808_143022.json
```