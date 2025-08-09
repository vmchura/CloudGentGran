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
import pyarrow as pa
import pyarrow.parquet as pq
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import os
import urllib.parse
from io import BytesIO

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_s3_client() -> boto3.client.S3:
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
    Main Lambda handler function triggered by S3 events
    
    Args:
        event: Lambda event data containing S3 event information
        context: Lambda context
        
    Returns:
        Dict containing execution results
    """
    try:
        logger.info(f"Starting transformation process at {datetime.utcnow()}")
        logger.info(f"Received event: {json.dumps(event, default=str)}")
        
        # Parse S3 event

        if 'downloaded_date' in event:
            downloaded_date = event['downloaded_date']
            bucket_name = os.environ['BUCKET_NAME']
            semantic_identifier = os.environ['SEMANTIC_IDENTIFIER']

            logger.info(f"Processing files: s3://{bucket_name}/{semantic_identifier}/downloaded_date={downloaded_date}")
            source_key = f"landing/{semantic_identifier}/downloaded_date={downloaded_date}"
            target_key = f"staging/{semantic_identifier}/transformed_date={downloaded_date}"
            result_dictionary = process_file(bucket_name, source_key, target_key)


            # Complete success
            return create_response(True, f"Successfully processed {len(processed_files)} files", result_dictionary)
        else:
            logger.error("No downloaded_date found in event")
            return create_response(False, "No downloaded_date found in event")
            
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return create_response(False, f"Handler error: {str(e)}")


def process_file(bucket: str, source_key: str, target_key: str) -> Dict[str, Any]:
    """
    Process a single file from landing to staging

        
    Returns:
        Dict with processing results
        :param source_key:
        :param bucket:
        :param target_key:
    """
    s3_client = get_s3_client()

    
    try:
        response = s3_client.list_objects_v2(Bucket=bucket, Prefix=source_key)

        keys = [
            obj["Key"]
            for obj in response.get("Contents", [])
            if re.fullmatch(rf"{re.escape(prefix)}\d{{8}}\.json", obj["Key"])
        ]
        dfs = []
        for key in keys:
            obj = s3.get_object(Bucket=bucket, Key=key)
            data_bytes = obj["Body"].read()
            df = pl.read_json(io.BytesIO(data_bytes))
            dfs.append(df)

        if dfs:
            df = pl.concat(dfs, how="vertical")
        else:
            logger.error(f"Error processing file {source_key}: maybe no data found?")
            raise


        # Convert to Parquet and upload
        upload_parquet_to_s3(df, target_bucket, target_key)
        
        logger.info(f"Successfully processed {source_key} -> {target_key}")
        logger.info(f"Transformed {len(df)} raw records to {len(df)} clean records")
        
        return {
            'source_key': source_key,
            'target_key': target_key,
            'status': 'success',
            'raw_records': len(df),
            'clean_records': len(df),
            'target_location': f's3://{target_bucket}/{target_key}'
        }
        
    except Exception as e:
        logger.error(f"Error processing file {source_key}: {str(e)}")
        raise


def transform_social_services_data(raw_data: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Transform raw social services data according to staging schema
    
    Args:
        raw_data: List of raw JSON records from the API
        
    Returns:
        Cleaned and transformed pandas DataFrame
    """
    if not raw_data:
        return pd.DataFrame()
    
    try:
        # Convert to DataFrame
        df = pd.DataFrame(raw_data)
        
        logger.info(f"Original DataFrame shape: {df.shape}")
        logger.info(f"Original columns: {list(df.columns)}")
        
        # Apply transformations
        df = clean_and_standardize_columns(df)
        df = validate_and_clean_data(df)
        df = deduplicate_records(df)
        df = add_metadata_columns(df)
        
        logger.info(f"Final DataFrame shape: {df.shape}")
        logger.info(f"Final columns: {list(df.columns)}")
        
        return df
        
    except Exception as e:
        logger.error(f"Error transforming data: {str(e)}")
        raise

def generate_staging_key(source_key: str, df: pd.DataFrame) -> str:
    """
    Generate S3 key for staging bucket with appropriate partitioning
    
    Args:
        source_key: Original S3 key from landing
        df: Transformed DataFrame
        
    Returns:
        S3 key for staging bucket
    """
    # Extract date from source key or use current date
    import re
    date_match = re.search(r'downloaded_at=(\d{8})', source_key)
    if date_match:
        partition_date = date_match.group(1)
    else:
        partition_date = datetime.utcnow().strftime('%Y%m%d')
    
    # Determine partition value (could be based on data content)
    # For now, we'll use the date as partition
    partition_value = partition_date
    
    # Generate unique filename
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    record_count = len(df)
    
    staging_key = f"staging/social_services/processed_date={partition_value}/social_services_{timestamp}_{record_count}records.parquet"
    
    return staging_key


def upload_parquet_to_s3(df: pl.DataFrame, bucket_name: str, s3_key: str) -> None:
    """
    Convert DataFrame to Parquet and upload to S3
    
    Args:
        df: DataFrame to convert and upload
        bucket_name: Target S3 bucket
        s3_key: Target S3 key
    """
    try:
        s3_client = get_s3_client()
        
        # Convert DataFrame to Parquet in memory
        parquet_buffer = BytesIO()
        
        # Define Parquet schema for better compression and query performance
        table = pa.Table.from_pandas(df)
        
        # Write to Parquet with optimizations
        pq.write_table(
            table,
            parquet_buffer,
            compression='snappy',  # Good balance of compression and speed
            use_dictionary=True,   # Better compression for categorical data
            row_group_size=10000,  # Optimize for typical query patterns
        )
        
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
                'columns': ','.join(df.columns.tolist())
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
