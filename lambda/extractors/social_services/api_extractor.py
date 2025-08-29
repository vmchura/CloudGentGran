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
        s3_keys = []
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
                        logger.info(f"Iteration {i + 1}: Processing {len(temporal_result)} records")
                        s3_key = upload_to_s3(bucket_name, raw_json_bytes, semantic_identifier, offset, downloaded_date)
                        s3_keys.append(s3_key)
                        total_records += len(temporal_result)
                        
            except Exception as e:
                logger.error(f"Error in iteration {i + 1}: {str(e)}")
                return create_response(False, f"Critical error in iteration {i + 1}: {str(e)}")

        if len(s3_keys) == 0:
            logger.error("No data extracted from API")
            return create_response(False, "No data extracted from API")

        logger.info(f"Successfully extracted {total_records} total records in {len(s3_keys)} files")

        # Return enhanced data for Airflow coordination
        logger.info("Successfully completed extraction - returning metadata for Airflow coordination")

        return create_response(True, f"Successfully processed {len(s3_keys)} blocks with {total_records} total records", {
            'bucket': bucket_name,
            'semantic_identifier': semantic_identifier,
            'downloaded_date': downloaded_date,
            'file_count': len(s3_keys),
            'total_records': total_records,
            's3_keys': s3_keys[:10],  # First 10 for reference
            'source_prefix': f"landing/{semantic_identifier}/downloaded_date={downloaded_date}/",
            'extraction_completed_at': datetime.utcnow().isoformat(),
            'next_step': 'trigger_transformer',  # Airflow coordination hint
            'transformer_payload': {
                'bucket_name': bucket_name,
                'semantic_identifier': semantic_identifier,
                'downloaded_date': downloaded_date,
                'file_count': len(s3_keys),
                'total_records': total_records,
                'source_prefix': f"landing/{semantic_identifier}/downloaded_date={downloaded_date}/",
                'extraction_timestamp': datetime.utcnow().isoformat()
            }
        })

    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return create_response(False, f"Error: {str(e)}")


def upload_to_s3(bucket_name: str, json_data: bytes, semantic_identifier: str, offset: int, downloaded_date: str) -> str:
    """
    Upload extracted data to S3 landing bucket
    
    Args:
        bucket_name: S3 bucket name
        json_data: Raw JSON data as bytes
        semantic_identifier: Semantic identifier for the dataset
        offset: Offset for the current batch
        downloaded_date: Date string (YYYYMMDD)
    
    Returns:
        S3 key of the uploaded file
    """
    try:
        s3_client = get_s3_client()

        # Generate S3 key with partitioning by download date
        s3_key = f"landing/{semantic_identifier}/downloaded_date={downloaded_date}/{offset:08d}.json"
        
        # Upload to S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json_data,
            ContentType='application/json',
            Metadata={
                'extractor': 'social-services-api-extractor',
                'semantic_identifier': semantic_identifier,
                'downloaded_date': downloaded_date,
                'offset': str(offset),
                'extraction_timestamp': datetime.utcnow().isoformat()
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