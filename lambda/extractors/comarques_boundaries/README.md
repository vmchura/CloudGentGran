# Comarques Boundaries API Extractor Lambda

This Lambda function extracts geographical boundaries for comarques (counties) and municipalities in Catalunya from the ICGC (Institut Cartogràfic i Geològic de Catalunya) and converts them to GeoJSON format.

## Overview

The comarques boundaries extractor downloads shapefile data from the ICGC, processes it to extract comarques and municipalities boundaries, converts the coordinates from ETRS89 (EPSG:25831) to WGS84 (EPSG:4326), and uploads the results as GeoJSON files to S3.

## Functionality

- Downloads administrative boundaries shapefile from ICGC
- Extracts shapefile components for comarques and municipalities
- Converts coordinates from ETRS89 to WGS84
- Generates GeoJSON FeatureCollections
- Uploads GeoJSON files to S3

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
  "message": "Successfully extracted comarques boundaries",
  "timestamp": "2024-01-01T00:00:00",
  "extractor": "comarques-boundaries-extractor",
  "data": {
    "bucket": "landing-bucket",
    "semantic_identifier": "comarques-boundaries",
    "list_s3_keys": [
      "landing/comarques-boundaries/comarques-1000000.json",
      "landing/comarques-boundaries/municipis-1000000.json"
    ],
    "extraction_completed_at": "2024-01-01T00:00:00"
  }
}
```

## Data Processing

The Lambda performs the following operations:
1. Downloads ZIP file from ICGC datacloud
2. Extracts shapefile components (.shp, .shx, .dbf, .prj)
3. Reads geometries and attributes using pyshp
4. Detects source CRS from PRJ file (defaults to EPSG:25831)
5. Transforms coordinates to EPSG:4326 using pyproj
6. Generates GeoJSON FeatureCollection for each level

For comarques: extracts `CODICOMAR` as `comarca_id`  
For municipalities: extracts `CODIMUNI` as `municipal_id`

## Error Handling

The Lambda includes specific error handling for:
- **ConfigurationError**: Missing required environment variables
- **DownloadError**: HTTP errors, URL errors, timeouts when downloading data
- **DataProcessingError**: Missing shapefile components, parsing errors, coordinate transformation errors
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
python -m pytest test_comarques_boundaries_api_extractor.py -v
```

Tests cover:
- S3 client configuration
- EPSG extraction from PRJ files
- Shape type to GeoJSON mapping
- Shape parts to rings conversion
- Coordinate transformation
- Response creation
- S3 upload functionality
- Download failure handling
- Missing shapefile components handling

## Data Source

The Lambda downloads data from:
```
https://datacloud.icgc.cat/datacloud/divisions-administratives/shp/divisions-administratives-v2r1-20250730.zip
```

## Dependencies

- `pyshp`: For reading shapefiles
- `pyproj`: For coordinate transformations

Install dependencies:
```bash
pip install pyshp pyproj
```
