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
from datetime import datetime, UTC
from typing import Dict, Any, List, Optional
import os
import sys
import pandas as pd
from io import BytesIO
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from common.exceptions import (
    LambdaError,
    ConfigurationError,
    APIError,
    DataValidationError,
    DataProcessingError,
    S3OperationError,
    ERROR_STATUS_CODES,
    get_current_time,
)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


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
    bucket_name = os.environ.get("CATALOG_BUCKET_NAME")
    dataset_identifier = os.environ.get("DATASET_IDENTIFIER")
    semantic_identifier = os.environ.get("SEMANTIC_IDENTIFIER")

    missing_vars = []
    if not bucket_name:
        missing_vars.append("CATALOG_BUCKET_NAME")
    if not dataset_identifier:
        missing_vars.append("DATASET_IDENTIFIER")
    if not semantic_identifier:
        missing_vars.append("SEMANTIC_IDENTIFIER")

    if missing_vars:
        raise ConfigurationError(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )

    return bucket_name, dataset_identifier, semantic_identifier  # type: ignore[return-value]


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
        logger.info(f"Starting API extraction process at {get_current_time()}")

        # Validate environment variables
        bucket_name, dataset_identifier, semantic_identifier = validate_environment()

        api_endpoint_institution = f"https://analisi.transparenciacatalunya.cat/resource/{dataset_identifier}.json"

        process_initiated_at = get_current_time()
        downloaded_date = process_initiated_at.strftime("%Y%m%d")
        list_json: List[Dict] = []
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
                    raise APIError(
                        f"HTTP {e.code} error at offset {offset}: {e.reason}"
                    )
                except urllib.error.URLError as e:
                    raise APIError(f"URL error at offset {offset}: {e.reason}")
                except TimeoutError:
                    raise APIError(f"Timeout error at offset {offset}")

                try:
                    raw_json_str = raw_json_bytes.decode("utf-8")
                    temporal_result = json.loads(raw_json_str)
                except json.JSONDecodeError as e:
                    raise DataValidationError(
                        f"Invalid JSON at offset {offset}: {str(e)}"
                    )
                except UnicodeDecodeError as e:
                    raise DataValidationError(
                        f"Invalid encoding at offset {offset}: {str(e)}"
                    )

                if not isinstance(temporal_result, list):
                    raise DataValidationError(
                        f"Expected list response at offset {offset}, got {type(temporal_result).__name__}"
                    )

                if len(temporal_result) == 0:
                    logger.info(
                        f"No more data available. Finished at iteration {i + 1}"
                    )
                    break
                else:
                    list_json.extend(temporal_result)
                    logger.info(
                        f"Iteration {i + 1}: Processing {len(temporal_result)} records"
                    )
                    total_records += len(temporal_result)

            except (APIError, DataValidationError):
                raise
            except Exception as e:
                logger.error(f"Unexpected error in iteration {i + 1}: {str(e)}")
                raise LambdaError(f"Unexpected error in iteration {i + 1}: {str(e)}")

        if len(list_json) == 0:
            raise DataValidationError("No data extracted from API")

        # Upload to S3
        s3_key = upload_to_s3(
            bucket_name, list_json, semantic_identifier, downloaded_date
        )

        logger.info(f"Successfully extracted {total_records} total records")

        # Return enhanced data for Airflow coordination
        logger.info(
            "Successfully completed extraction - returning metadata for Airflow coordination"
        )

        return create_response(
            True,
            f"Successfully processed {total_records} records",
            {
                "bucket": bucket_name,
                "semantic_identifier": semantic_identifier,
                "downloaded_date": downloaded_date,
                "total_records": total_records,
                "s3_key": s3_key,
                "extraction_completed_at": get_current_time().isoformat(),
                "next_step": "trigger_transformer",  # Airflow coordination hint
                "transformer_payload": {
                    "bucket_name": bucket_name,
                    "semantic_identifier": semantic_identifier,
                    "downloaded_date": downloaded_date,
                    "total_records": total_records,
                    "source_prefix": f"catalog/municipals/",
                    "extraction_timestamp": get_current_time().isoformat(),
                },
            },
        )

    except ConfigurationError as e:
        logger.error(f"Configuration error: {str(e)}")
        return create_response(
            False,
            str(e),
            error_type="ConfigurationError",
        )
    except APIError as e:
        logger.error(f"API error: {str(e)}")
        return create_response(
            False,
            str(e),
            error_type="APIError",
        )
    except DataValidationError as e:
        logger.error(f"Data validation error: {str(e)}")
        return create_response(
            False,
            str(e),
            error_type="DataValidationError",
        )
    except DataProcessingError as e:
        logger.error(f"Data processing error: {str(e)}")
        return create_response(
            False,
            str(e),
            error_type="DataProcessingError",
        )
    except S3OperationError as e:
        logger.error(f"S3 operation error: {str(e)}")
        return create_response(
            False,
            str(e),
            error_type="S3OperationError",
        )
    except LambdaError as e:
        logger.error(f"Lambda error: {str(e)}")
        return create_response(
            False,
            str(e),
            error_type=type(e).__name__,
        )
    except (ClientError, NoCredentialsError, EndpointConnectionError) as e:
        logger.error(f"AWS service error: {str(e)}")
        return create_response(
            False,
            "AWS service error",
            {"message": "Failed to connect to AWS services"},
            error_type=type(e).__name__,
        )
    except Exception as e:
        logger.error(f"Unexpected error in lambda_handler: {str(e)}")
        return create_response(
            False,
            "An unexpected error occurred",
            error_type=type(e).__name__,
        )


def upload_dataframe_to_s3(bucket_name: str, df: pd.DataFrame, table_name: str) -> str:
    """
    Upload processed DataFrame to S3 as parquet

    Args:
        bucket_name: S3 bucket name
        df: Processed DataFrame ready for upload
        table_name: Semantic identifier for the dataset

    Returns:
        S3 key of the uploaded file
    """
    try:
        s3_client = get_s3_client()
        current_time = get_current_time().isoformat()
        s3_key = f"{table_name}/municipals.parquet"

        # Convert DataFrame to parquet in memory
        parquet_buffer = BytesIO()
        df.to_parquet(parquet_buffer, engine="fastparquet", index=False)
        parquet_buffer.seek(0)

        # Upload to S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=parquet_buffer.getvalue(),
            ContentType="application/octet-stream",
            Metadata={
                "table_name": table_name,
                "record_count": str(len(df)),
                "created_at": current_time,
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
        logger.error(f"Failed to upload DataFrame to S3: {str(e)}")
        raise S3OperationError(f"S3 upload failed: {str(e)}")


def upload_to_s3(
    bucket_name: str, json_data: list, table_name: str, downloaded_date: str
) -> str:
    """
    Process and upload extracted data to S3 landing bucket

    Args:
        bucket_name: S3 bucket name
        json_data: List of JSON records
        table_name: Semantic identifier for the dataset
        downloaded_date: Date string (YYYYMMDD)

    Returns:
        S3 key of the uploaded file
    """
    try:
        # Process the JSON data into a clean DataFrame
        df = process_municipal_data(json_data)

        # Upload to S3 with all metadata included
        s3_key = upload_dataframe_to_s3(bucket_name, df, table_name)

        # Add additional metadata to the uploaded object
        s3_client = get_s3_client()

        # Get the existing object to preserve its body
        response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
        body = response["Body"].read()

        # Update the object with additional metadata
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=body,
            ContentType="application/octet-stream",
            Metadata={
                "table_name": table_name,
                "record_count": str(len(df)),
                "created_at": get_current_time().isoformat(),
            },
        )

        return s3_key

    except S3OperationError:
        raise
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        logger.error(f"AWS S3 error ({error_code}): {error_message}")
        raise S3OperationError(f"S3 operation failed: {error_message}")
    except Exception as e:
        logger.error(f"Failed to upload to S3: {str(e)}")
        raise S3OperationError(f"S3 operation failed: {str(e)}")


def process_municipal_data(json_data: list) -> pd.DataFrame:
    """
    Process municipal JSON data into a clean DataFrame with proper column names

    Args:
        json_data: List of JSON records from the API

    Returns:
        Processed DataFrame with standardized column names
    """
    try:
        # Create DataFrame from the JSON data
        df = pd.DataFrame(json_data)

        if df.empty:
            raise DataProcessingError("No data to process")

        # Filter columns if they exist (made optional to handle different data structures)
        available_columns = ["codi", "nom", "codi_comarca", "nom_comarca"]
        existing_columns = [col for col in available_columns if col in df.columns]
        if existing_columns:
            df = df[existing_columns]

        # Rename columns to match the target schema
        column_mapping = {
            "codi": "municipal_id",
            "nom": "municipal_name",
            "codi_comarca": "comarca_id",
            "nom_comarca": "comarca_name",
        }

        # Only rename columns that exist
        existing_mapping = {k: v for k, v in column_mapping.items() if k in df.columns}
        if existing_mapping:
            df = df.rename(columns=existing_mapping)

        return df
    except DataProcessingError:
        raise
    except Exception as e:
        logger.error(f"Error processing municipal data: {str(e)}")
        raise DataProcessingError(f"Failed to process municipal data: {str(e)}")


def create_response(
    success: bool,
    message: str,
    data: Optional[Dict[str, Any]] = None,
    error_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create standardized Lambda response

    Args:
        success: Whether the operation was successful
        message: Response message
        data: Optional additional data
        error_type: Optional error type for error responses

    Returns:
        Formatted response dictionary
    """
    status_code = 200 if success else 500

    if error_type:
        for exc_type, code in ERROR_STATUS_CODES.items():
            if exc_type.__name__ == error_type:
                status_code = code
                break

    response: Dict[str, Any] = {
        "statusCode": status_code,
        "success": success,
        "message": message,
        "timestamp": get_current_time().isoformat(),
        "extractor": "social-services-api-extractor",
    }

    if data:
        response["data"] = data

    if error_type:
        if "data" not in response:
            response["data"] = {}
        response["data"]["error_type"] = error_type

    return response
