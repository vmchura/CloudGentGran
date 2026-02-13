"""
Catalunya Data Pipeline - Public API Extractor
This Lambda function extracts data from a public API and writes to the landing S3 bucket.
Returns extraction metadata for Airflow orchestration coordination.
https://analisi.transparenciacatalunya.cat/Societat-benestar/Registre-d-entitats-serveis-i-establiments-socials/ivft-vegh/about_data
"""

import json
import boto3
import urllib.request
import urllib.error
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import os
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


class SocialServicesExtractorError(Exception):
    """Base exception for social services extractor errors"""

    pass


class ConfigurationError(SocialServicesExtractorError):
    """Raised when there's a configuration error"""

    pass


class APIError(SocialServicesExtractorError):
    """Raised when API requests fail"""

    pass


class S3OperationError(SocialServicesExtractorError):
    """Raised when S3 operations fail"""

    pass


class DataValidationError(SocialServicesExtractorError):
    """Raised when data validation fails"""

    pass


def get_s3_client():
    """Get S3 client with optional endpoint URL for LocalStack"""
    endpoint_url = os.environ.get("AWS_ENDPOINT_URL")
    if endpoint_url:
        logger.info(f"Using S3 endpoint: {endpoint_url}")
        return boto3.client("s3", endpoint_url=endpoint_url)
    else:
        logger.info("Using default S3 endpoint")
        return boto3.client("s3")


def validate_environment() -> tuple[str, str, str]:
    """Validate required environment variables"""
    bucket_name = os.environ.get("BUCKET_NAME")
    dataset_identifier = os.environ.get("DATASET_IDENTIFIER")
    semantic_identifier = os.environ.get("SEMANTIC_IDENTIFIER")

    missing_vars = []
    if not bucket_name:
        missing_vars.append("BUCKET_NAME")
    if not dataset_identifier:
        missing_vars.append("DATASET_IDENTIFIER")
    if not semantic_identifier:
        missing_vars.append("SEMANTIC_IDENTIFIER")

    if missing_vars:
        raise ConfigurationError(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )

    return bucket_name, dataset_identifier, semantic_identifier


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

        # Validate environment variables
        bucket_name, dataset_identifier, semantic_identifier = validate_environment()

        api_endpoint_institution = f"https://analisi.transparenciacatalunya.cat/resource/{dataset_identifier}.json"

        process_initiated_at = datetime.utcnow()
        downloaded_date = process_initiated_at.strftime("%Y%m%d")
        s3_keys: List[str] = []
        total_records = 0

        logger.info(f"Starting download for date: {downloaded_date}")

        # Download data in batches
        for i in range(100):  # Safety limit to prevent infinite loops
            try:
                offset = i * 1000
                url = f"{api_endpoint_institution}?$offset={offset}"
                logger.info(f"Fetching data from: {url}")

                try:
                    with urllib.request.urlopen(url, timeout=30) as http_response:
                        raw_json_bytes = http_response.read()
                except urllib.error.HTTPError as e:
                    raise APIError(f"HTTP {e.code} error fetching data: {e.reason}")
                except urllib.error.URLError as e:
                    raise APIError(f"URL error fetching data: {e.reason}")
                except TimeoutError:
                    raise APIError("Request timeout while fetching data")

                try:
                    raw_json_str = raw_json_bytes.decode("utf-8")
                    temporal_result = json.loads(raw_json_str)
                except json.JSONDecodeError as e:
                    raise DataValidationError(f"Invalid JSON response: {str(e)}")
                except UnicodeDecodeError as e:
                    raise DataValidationError(f"Invalid encoding in response: {str(e)}")

                if not isinstance(temporal_result, list):
                    raise DataValidationError(
                        f"Expected list response, got {type(temporal_result).__name__}"
                    )

                if len(temporal_result) == 0:
                    logger.info(
                        f"No more data available. Finished at iteration {i + 1}"
                    )
                    break
                else:
                    logger.info(
                        f"Iteration {i + 1}: Processing {len(temporal_result)} records"
                    )
                    s3_key = upload_to_s3(
                        bucket_name,
                        raw_json_bytes,
                        semantic_identifier,
                        offset,
                        downloaded_date,
                    )
                    s3_keys.append(s3_key)
                    total_records += len(temporal_result)

            except (APIError, DataValidationError, S3OperationError):
                raise
            except Exception as e:
                logger.error(f"Unexpected error in iteration {i + 1}: {str(e)}")
                raise SocialServicesExtractorError(
                    f"Unexpected error in iteration {i + 1}: {str(e)}"
                )

        if len(s3_keys) == 0:
            raise DataValidationError("No data extracted from API")

        logger.info(
            f"Successfully extracted {total_records} total records in {len(s3_keys)} files"
        )

        # Return enhanced data for Airflow coordination
        logger.info(
            "Successfully completed extraction - returning metadata for Airflow coordination"
        )

        return create_response(
            True,
            f"Successfully processed {len(s3_keys)} blocks with {total_records} total records",
            {
                "bucket": bucket_name,
                "semantic_identifier": semantic_identifier,
                "downloaded_date": downloaded_date,
                "file_count": len(s3_keys),
                "total_records": total_records,
                "s3_keys": s3_keys[:10],  # First 10 for reference
                "source_prefix": f"landing/{semantic_identifier}/downloaded_date={downloaded_date}/",
                "extraction_completed_at": datetime.utcnow().isoformat(),
                "next_step": "trigger_transformer",  # Airflow coordination hint
                "transformer_payload": {
                    "bucket_name": bucket_name,
                    "semantic_identifier": semantic_identifier,
                    "downloaded_date": downloaded_date,
                    "file_count": len(s3_keys),
                    "total_records": total_records,
                    "source_prefix": f"landing/{semantic_identifier}/downloaded_date={downloaded_date}/",
                    "extraction_timestamp": datetime.utcnow().isoformat(),
                },
            },
        )

    except ConfigurationError as e:
        logger.error(f"Configuration error: {str(e)}")
        return create_response(False, str(e), {"error_type": "ConfigurationError"})
    except APIError as e:
        logger.error(f"API error: {str(e)}")
        return create_response(False, str(e), {"error_type": "APIError"})
    except DataValidationError as e:
        logger.error(f"Data validation error: {str(e)}")
        return create_response(False, str(e), {"error_type": "DataValidationError"})
    except S3OperationError as e:
        logger.error(f"S3 operation error: {str(e)}")
        return create_response(False, str(e), {"error_type": "S3OperationError"})
    except (ClientError, NoCredentialsError, EndpointConnectionError) as e:
        logger.error(f"AWS service error: {str(e)}")
        return create_response(
            False,
            "AWS service error",
            {
                "error_type": type(e).__name__,
                "message": "Failed to connect to AWS services",
            },
        )
    except SocialServicesExtractorError as e:
        logger.error(f"Extractor error: {str(e)}")
        return create_response(
            False, str(e), {"error_type": "SocialServicesExtractorError"}
        )
    except Exception as e:
        logger.error(f"Unexpected error in lambda_handler: {str(e)}")
        return create_response(
            False, "An unexpected error occurred", {"error_type": type(e).__name__}
        )


def upload_to_s3(
    bucket_name: str,
    json_data: bytes,
    semantic_identifier: str,
    offset: int,
    downloaded_date: str,
) -> str:
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

    Raises:
        S3OperationError: If S3 upload fails
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
            ContentType="application/json",
            Metadata={
                "extractor": "social-services-api-extractor",
                "semantic_identifier": semantic_identifier,
                "downloaded_date": downloaded_date,
                "offset": str(offset),
                "extraction_timestamp": datetime.utcnow().isoformat(),
            },
        )

        logger.info(f"Successfully uploaded to s3://{bucket_name}/{s3_key}")
        return s3_key

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        logger.error(f"AWS S3 error ({error_code}): {error_message}")
        raise S3OperationError(f"S3 upload failed: {error_message}")
    except Exception as e:
        logger.error(f"Failed to upload to S3: {str(e)}")
        raise S3OperationError(f"S3 upload failed: {str(e)}")


def create_response(
    success: bool, message: str, data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create standardized Lambda response

    Args:
        success: Whether the operation was successful
        message: Response message
        data: Optional additional data

    Returns:
        Formatted response dictionary
    """
    response: Dict[str, Any] = {
        "statusCode": 200 if success else 500,
        "success": success,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
        "extractor": "social-services-api-extractor",
    }

    if data:
        response["data"] = data

    return response
