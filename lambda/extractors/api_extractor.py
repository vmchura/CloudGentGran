"""
Catalunya Data Pipeline - Public API Extractor
This Lambda function extracts data from a public API and writes to the landing S3 bucket.
"""

import json
import boto3
import requests
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
        api_url = os.environ.get('API_URL', 'https://jsonplaceholder.typicode.com/posts')
        api_name = os.environ.get('API_NAME', 'jsonplaceholder')
        
        logger.info(f"Configuration: bucket={bucket_name}, api_url={api_url}, api_name={api_name}")
        
        # Extract data from API
        data = extract_from_api(api_url)
        
        if not data:
            logger.warning("No data extracted from API")
            return create_response(False, "No data extracted from API")
        
        # Upload to S3
        s3_key = upload_to_s3(bucket_name, data, api_name)
        
        logger.info(f"Successfully extracted {len(data)} records and uploaded to s3://{bucket_name}/{s3_key}")
        
        return create_response(True, f"Successfully processed {len(data)} records", {
            'bucket': bucket_name,
            's3_key': s3_key,
            'records_count': len(data)
        })
        
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return create_response(False, f"Error: {str(e)}")

def extract_from_api(api_url: str) -> List[Dict[str, Any]]:
    """
    Extract data from the public API
    
    Args:
        api_url: URL of the API to extract from
        
    Returns:
        List of extracted records
    """
    try:
        logger.info(f"Making API request to: {api_url}")
        
        # Make the API request with timeout
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()
        
        # Parse JSON response
        data = response.json()
        
        # Ensure we have a list of records
        if isinstance(data, dict):
            data = [data]
        
        logger.info(f"Successfully extracted {len(data)} records from API")
        return data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {str(e)}")
        raise

def upload_to_s3(bucket_name: str, data: List[Dict[str, Any]], api_name: str) -> str:
    """
    Upload extracted data to S3 landing bucket
    
    Args:
        bucket_name: Name of the S3 bucket
        data: Data to upload
        api_name: Name of the API (for file naming)
        
    Returns:
        S3 key of the uploaded file
    """
    try:
        # Get S3 client (reads environment variables at runtime)
        s3_client = get_s3_client()
        
        # Generate S3 key with timestamp
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        s3_key = f"landing/{api_name}/year={datetime.utcnow().year}/month={datetime.utcnow().month:02d}/day={datetime.utcnow().day:02d}/{api_name}_{timestamp}.json"
        
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
                'api_name': api_name,
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
