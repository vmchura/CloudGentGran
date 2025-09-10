"""
Catalunya Data Pipeline - Public API Extractor
This Lambda function extracts data from a public API and writes to the landing S3 bucket.
Returns extraction metadata for Airflow orchestration coordination.
https://analisi.transparenciacatalunya.cat/Societat-benestar/Registre-d-entitats-serveis-i-establiments-socials/ivft-vegh/about_data
"""

import json
import boto3
import urllib.request
import logging
from datetime import datetime
from typing import Dict, Any, List
import os
import pandas as pd
# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_s3_client():
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
    Main Lambda handler function

    Args:
        event: Lambda event data
        context: Lambda context

    Returns:
        Dict containing execution results
    """
    try:
        logger.info(f"Starting API extraction process at {datetime.utcnow()}")
        
        # Get configuration from environment variables
        bucket_name = os.environ['BUCKET_NAME']
        dataset_identifier = os.environ['DATASET_IDENTIFIER']
        semantic_identifier = os.environ['SEMANTIC_IDENTIFIER']
        api_endpoint_institution = f'https://analisi.transparenciacatalunya.cat/resource/{dataset_identifier}.json'

        process_initiated_at = datetime.utcnow()
        downloaded_date = process_initiated_at.strftime('%Y%m%d')
        list_json = []
        total_records = 0

        logger.info(f"Starting download for date: {downloaded_date}")

        # Download data in batches
        for i in range(100):  # Safety limit to prevent infinite loops
            try:
                offset = i * 1000
                url = f"{api_endpoint_institution}?$offset={offset}"
                logger.info(f"Fetching data from: {url}")
                
                with urllib.request.urlopen(url) as http_response:
                    raw_json_bytes = http_response.read()
                    raw_json_str = raw_json_bytes.decode("utf-8")
                    temporal_result = json.loads(raw_json_str)
                    if len(temporal_result) == 0:
                        logger.info(f"No more data available. Finished at iteration {i + 1}")
                        break
                    else:
                        list_json.append(temporal_result)
                        logger.info(f"Iteration {i + 1}: Processing {len(temporal_result)} records")

                        total_records += len(temporal_result)
                        
            except Exception as e:
                logger.error(f"Error in iteration {i + 1}: {str(e)}")
                return create_response(False, f"Critical error in iteration {i + 1}: {str(e)}")

        if len(list_json) == 0:
            logger.error("No data extracted from API")
            return create_response(False, "No data extracted from API")

        logger.info(f"Successfully extracted {total_records} total records in {len(s3_keys)} files")
        s3_key = upload_to_s3(bucket_name, list_json, semantic_identifier, downloaded_date)
        # Return enhanced data for Airflow coordination
        logger.info("Successfully completed extraction - returning metadata for Airflow coordination")

        return create_response(True, f"Successfully processed {len(s3_keys)} blocks with {total_records} total records", {
            'bucket': bucket_name,
            'semantic_identifier': semantic_identifier,
            'downloaded_date': downloaded_date,
            'total_records': total_records,
            's3_key': s3_key,
            'extraction_completed_at': datetime.utcnow().isoformat(),
            'next_step': 'trigger_transformer',  # Airflow coordination hint
            'transformer_payload': {
                'bucket_name': bucket_name,
                'semantic_identifier': semantic_identifier,
                'downloaded_date': downloaded_date,
                'total_records': total_records,
                'source_prefix': f"catalog/municipals/",
                'extraction_timestamp': datetime.utcnow().isoformat()
            }
        })

    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return create_response(False, f"Error: {str(e)}")


def upload_to_s3(bucket_name: str, json_data: list, table_name: str, downloaded_date: str) -> str:
    """
    Upload extracted data to S3 landing bucket
    
    Args:
        bucket_name: S3 bucket name
        json_data: Raw JSON data as bytes
        table_name: Semantic identifier for the dataset
        downloaded_date: Date string (YYYYMMDD)
    
    Returns:
        S3 key of the uploaded file
    """
    try:
        s3_client = get_s3_client()

        # Generate S3 key with partitioning by download date
        s3_key = f"catalog/municipals/{downloaded_date}.parquet"
        df = pd.DataFrame(json_data)['codi', 'nom', 'codi_comarca', 'nom_comarca']
        current_time = datetime.utcnow().isoformat()
        df['created_at'] = current_time

        # Create S3 key with timestamp for uniqueness
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        s3_key = f"{table_name}/{timestamp}.parquet"

        # Convert DataFrame to parquet in memory
        parquet_buffer = BytesIO()
        df.to_parquet(parquet_buffer, engine='fastparquet', index=False)
        parquet_buffer.seek(0)

        # Upload to S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=parquet_buffer.getvalue(),
            ContentType='application/octet-stream',
            Metadata={
                'table_name': table_name,
                'record_count': str(len(df)),
                'created_at': current_time,
                'original_columns': json.dumps(list(data[0].keys()) if data else [])
            }
        )

        logger.info(f"Successfully uploaded to s3://{bucket_name}/{s3_key}")
        return s3_key

    except Exception as e:
        logger.error(f"Failed to upload to S3: {str(e)}")
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
        'extractor': 'social-services-api-extractor'
    }

    if data:
        response['data'] = data

    return response