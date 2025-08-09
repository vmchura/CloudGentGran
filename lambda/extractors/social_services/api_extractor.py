"""
Catalunya Data Pipeline - Public API Extractor
This Lambda function extracts data from a public API and writes to the landing S3 bucket.
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
        api_endpoint_institution = f'https://analisi.transparenciacatalunya.cat/resource/{dataset_identifier}.json'

        data = []

        for i in range(100):
            with urllib.request.urlopen(f"{api_endpoint_institution}?$offset={i * 1000}") as url:
                temporal_result = json.load(url)
                if len(temporal_result) == 0:
                    logger.info(f"Finished at iteration {i + 1}: total registers read {len(data)} from api entities\n")
                    break
                else:
                    logger.info(f"Iteration {i + 1}: read {len(temporal_result)} registers from api entities\n")
                    data = data + temporal_result

        if len(data) == 0:
            logger.error("No data extracted from API")
            return create_response(False, "No data extracted from API")

        s3_key = upload_to_s3(bucket_name, data, dataset_identifier)

        logger.info(f"Successfully extracted {len(data)} records and uploaded to s3://{bucket_name}/{s3_key}")


        return create_response(True, f"Successfully processed {len(data)} records", {
            'bucket': bucket_name,
            's3_key': s3_key,
            'records_count': len(data)
        })

    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return create_response(False, f"Error: {str(e)}")


def upload_to_s3(bucket_name: str, data: List[Dict[str, Any]], dataset_identifier: str) -> str:
    """
    Upload extracted data to S3 landing bucket

    Args:
        bucket_name: Name of the S3 bucket
        data: Data to upload
        dataset_identifier: Dataset identifier (for file naming)

    Returns:
        S3 key of the uploaded file
    """
    try:
        # Get S3 client (reads environment variables at runtime)
        s3_client = get_s3_client()

        # Generate S3 key with timestamp
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        semantic_identifier = os.environ.get('SEMANTIC_IDENTIFIER')
        s3_key = f"landing/{semantic_identifier}/downloaded_at={datetime.utcnow().strftime('%Y%m%d')}/{semantic_identifier}_{timestamp}.json"

        # Convert data to JSON
        json_data = json.dumps(data, indent=2, default=str)

        # Upload to S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json_data,
            ContentType='application/json',
            Metadata={
                'extractor': 'api-extractor',
                'dataset_identifier': dataset_identifier,
                'extraction_timestamp': timestamp,
                'records_count': str(len(data))
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
        'timestamp': datetime.utcnow().isoformat()
    }

    if data:
        response['data'] = data

    return response
