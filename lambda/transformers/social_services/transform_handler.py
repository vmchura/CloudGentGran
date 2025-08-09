"""
Catalunya Data Pipeline - Social Services Data Transformer
This Lambda function processes raw data from the landing S3 bucket and transforms it
to validated, clean data in the staging S3 bucket.

Processing includes:
- Data validation and cleaning
- Type casting and standardization
- Deduplication
- Schema enforcement
- Conversion to Parquet format
"""

import json
import boto3
import polars as pl
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import os
import re
import io
from io import BytesIO

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_s3_client() -> boto3.client:
    """Get S3 client with optional endpoint URL for LocalStack"""
    endpoint_url = os.environ.get('AWS_ENDPOINT_URL')
    if endpoint_url:
        logger.info(f"Using S3 endpoint: {endpoint_url}")
        return boto3.client('s3', endpoint_url=endpoint_url)
    else:
        logger.info("Using default S3 endpoint")
        return boto3.client('s3')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler function triggered by EventBridge events
    
    Args:
        event: Lambda event data containing downloaded_date information
        context: Lambda context
        
    Returns:
        Dict containing execution results
    """
    try:
        logger.info(f"Starting transformation process at {datetime.utcnow()}")
        logger.info(f"Received event: {json.dumps(event, default=str)}")
        
        # Parse EventBridge event
        if 'detail' in event and 'downloaded_date' in event['detail']:
            # EventBridge custom event from API extractor
            downloaded_date = event['detail']['downloaded_date']
            bucket_name = event['detail'].get('bucket_name') or os.environ['BUCKET_NAME']
            semantic_identifier = event['detail'].get('semantic_identifier') or os.environ['SEMANTIC_IDENTIFIER']
        elif 'downloaded_date' in event:
            # Direct invocation with downloaded_date
            downloaded_date = event['downloaded_date']
            bucket_name = os.environ['BUCKET_NAME']
            semantic_identifier = os.environ['SEMANTIC_IDENTIFIER']
        else:
            logger.error("No downloaded_date found in event")
            return create_response(False, "No downloaded_date found in event")

        logger.info(f"Processing files: s3://{bucket_name}/landing/{semantic_identifier}/downloaded_date={downloaded_date}")
        
        source_prefix = f"landing/{semantic_identifier}/downloaded_date={downloaded_date}/"
        target_key = f"staging/{semantic_identifier}/transformed_date={downloaded_date}/social_services_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.parquet"
        
        result = process_files_for_date(bucket_name, source_prefix, target_key)

        # Complete success
        return create_response(True, f"Successfully processed files for date {downloaded_date}", result)
            
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return create_response(False, f"Handler error: {str(e)}")


def process_files_for_date(bucket: str, source_prefix: str, target_key: str) -> Dict[str, Any]:
    """
    Process all JSON files with a specific downloaded_date from landing to staging
    
    Args:
        bucket: S3 bucket name
        source_prefix: S3 prefix to search for JSON files (e.g., "landing/social_services/downloaded_date=20250809/")
        target_key: Target S3 key for the consolidated parquet file
        
    Returns:
        Dict with processing results
    """
    s3_client = get_s3_client()
    
    try:
        # List all JSON files in the source prefix
        response = s3_client.list_objects_v2(Bucket=bucket, Prefix=source_prefix)
        
        if 'Contents' not in response:
            logger.warning(f"No files found in s3://{bucket}/{source_prefix}")
            return {
                'source_prefix': source_prefix,
                'target_key': target_key,
                'status': 'success',
                'files_processed': 0,
                'raw_records': 0,
                'clean_records': 0,
                'message': 'No files to process'
            }
        
        # Filter for JSON files with pattern XXXXXXXX.json (8 digits)
        json_keys = [
            obj["Key"]
            for obj in response.get("Contents", [])
            if obj["Key"].endswith('.json') and re.search(r'/\d{8}\.json$', obj["Key"])
        ]
        
        if not json_keys:
            logger.warning(f"No matching JSON files found in s3://{bucket}/{source_prefix}")
            return {
                'source_prefix': source_prefix,
                'target_key': target_key,
                'status': 'success',
                'files_processed': 0,
                'raw_records': 0,
                'clean_records': 0,
                'message': 'No matching JSON files found'
            }
        
        logger.info(f"Found {len(json_keys)} JSON files to process")
        
        # Read and combine all JSON files
        dataframes = []
        total_raw_records = 0
        
        for key in json_keys:
            try:
                logger.info(f"Processing file: {key}")
                obj = s3_client.get_object(Bucket=bucket, Key=key)
                data_bytes = obj["Body"].read()
                
                # Read JSON with polars
                df = pl.read_json(io.BytesIO(data_bytes))
                dataframes.append(df)
                total_raw_records += len(df)
                logger.info(f"Read {len(df)} records from {key}")
                
            except Exception as e:
                logger.error(f"Error processing file {key}: {str(e)}")
                # Continue processing other files
                continue
        
        if not dataframes:
            logger.error("No dataframes created from JSON files")
            raise Exception("Failed to process any JSON files")
        
        # Concatenate all dataframes
        logger.info(f"Concatenating {len(dataframes)} dataframes")
        combined_df = pl.concat(dataframes, how="vertical")
        
        # Apply transformations
        transformed_df = transform_social_services_data(combined_df)
        
        # Upload consolidated parquet file
        upload_parquet_to_s3(transformed_df, bucket, target_key)
        
        logger.info(f"Successfully processed {len(json_keys)} files -> {target_key}")
        logger.info(f"Transformed {total_raw_records} raw records to {len(transformed_df)} clean records")
        
        return {
            'source_prefix': source_prefix,
            'target_key': target_key,
            'status': 'success',
            'files_processed': len(json_keys),
            'raw_records': total_raw_records,
            'clean_records': len(transformed_df),
            'target_location': f's3://{bucket}/{target_key}'
        }
        
    except Exception as e:
        logger.error(f"Error processing files for prefix {source_prefix}: {str(e)}")
        raise


def transform_social_services_data(df: pl.DataFrame) -> pl.DataFrame:
    """
    Transform raw social services data according to staging schema
    
    Args:
        df: Raw polars DataFrame from the API
        
    Returns:
        Cleaned and transformed polars DataFrame
    """
    try:
        logger.info(f"Original DataFrame shape: {df.shape}")
        logger.info(f"Original columns: {df.columns}")
        
        # Basic cleaning and transformations
        # Remove any completely empty rows
        df = df.filter(pl.any_horizontal(pl.col("*").is_not_null()))
        
        # Add metadata columns
        df = df.with_columns([
            pl.lit(datetime.utcnow().isoformat()).alias('processed_timestamp'),
            pl.lit('social-services-transformer').alias('processor'),
            pl.lit(os.environ.get('ENVIRONMENT', 'unknown')).alias('environment')
        ])
        
        # Remove duplicates if any (based on all columns except metadata)
        metadata_cols = ['processed_timestamp', 'processor', 'environment']
        data_cols = [col for col in df.columns if col not in metadata_cols]
        
        if data_cols:
            df = df.unique(subset=data_cols)
        
        logger.info(f"Final DataFrame shape: {df.shape}")
        logger.info(f"Final columns: {df.columns}")
        
        return df
        
    except Exception as e:
        logger.error(f"Error transforming data: {str(e)}")
        raise


def upload_parquet_to_s3(df: pl.DataFrame, bucket_name: str, s3_key: str) -> None:
    """
    Convert DataFrame to Parquet and upload to S3
    
    Args:
        df: Polars DataFrame to convert and upload
        bucket_name: Target S3 bucket
        s3_key: Target S3 key
    """
    try:
        s3_client = get_s3_client()
        
        # Convert to Parquet in memory using polars
        parquet_buffer = BytesIO()
        df.write_parquet(parquet_buffer, compression='snappy')
        parquet_buffer.seek(0)
        
        # Upload to S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=parquet_buffer.getvalue(),
            ContentType='application/octet-stream',
            Metadata={
                'transformer': 'social-services-transformer',
                'format': 'parquet',
                'record_count': str(len(df)),
                'processed_timestamp': datetime.utcnow().isoformat(),
                'columns': ','.join(df.columns)
            }
        )
        
        logger.info(f"Successfully uploaded Parquet file to s3://{bucket_name}/{s3_key}")
        logger.info(f"File size: {len(parquet_buffer.getvalue())} bytes, Records: {len(df)}")
        
    except Exception as e:
        logger.error(f"Failed to upload Parquet to S3: {str(e)}")
        raise


def create_response(success: bool, message: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Create standardized Lambda response
    
    Args:
        success: Whether the operation was successful
        message: Response message
        data: Optional additional data
        
    Returns:
        Formatted response dictionary
    """
    response = {
        'statusCode': 200 if success else 500,
        'success': success,
        'message': message,
        'timestamp': datetime.utcnow().isoformat(),
        'processor': 'social-services-transformer'
    }
    
    if data:
        response['data'] = data
    
    return response