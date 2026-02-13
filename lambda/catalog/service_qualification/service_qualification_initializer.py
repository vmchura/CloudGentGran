import json
import boto3
import pandas as pd
import os
import sys
from typing import Dict, List, Any, Optional
import logging
from io import BytesIO
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from common.exceptions import (
    LambdaError,
    ConfigurationError,
    DataProcessingError,
    S3OperationError,
    ERROR_STATUS_CODE_NAMES,
    get_current_time,
)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


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
        status_code = ERROR_STATUS_CODE_NAMES.get(error_type, status_code)

    response: Dict[str, Any] = {
        "statusCode": status_code,
        "success": success,
        "message": message,
        "timestamp": get_current_time().isoformat(),
        "service": "service-qualification-initializer",
    }

    if data:
        response["data"] = data

    if error_type:
        if "data" not in response:
            response["data"] = {}
        response["data"]["error_type"] = error_type

    return response


def lambda_handler(event, context):
    """
    Simplified Lambda function to create raw parquet files from input data.

    This function takes input data and creates parquet files directly in S3
    without any AWS Glue integration.
    """

    try:
        # Get environment variables
        catalog_bucket = os.environ.get("CATALOG_BUCKET_NAME")
        if not catalog_bucket:
            raise ConfigurationError(
                "CATALOG_BUCKET_NAME environment variable is required"
            )

        # Initialize S3 client
        s3_client = boto3.client("s3")

        # Parse event
        table_name = event.get("table_name")
        if not table_name:
            raise DataProcessingError("table_name is required")

        table_data = [
            {
                "service_qualification_id": "PUB-001",
                "service_qualification_description": "Entitat d'iniciativa pública",
            },
            {
                "service_qualification_id": "PRV-001",
                "service_qualification_description": "Entitat privada d'iniciativa mercantil",
            },
            {
                "service_qualification_id": "PRV-002",
                "service_qualification_description": "Entitat privada d'iniciativa social",
            },
        ]

        logger.info(
            f"Creating parquet file for table: {table_name} with {len(table_data)} records"
        )

        # Create parquet file
        result = create_parquet_file(s3_client, catalog_bucket, table_name, table_data)

        logger.info(f"Successfully created parquet file for table: {table_name}")
        return result

    except ConfigurationError as e:
        logger.error(f"Configuration error: {str(e)}")
        return create_response(
            False,
            str(e),
            error_type="ConfigurationError",
        )
    except S3OperationError as e:
        logger.error(f"S3 operation error: {str(e)}")
        return create_response(
            False,
            str(e),
            error_type="S3OperationError",
        )
    except DataProcessingError as e:
        logger.error(f"Data processing error: {str(e)}")
        return create_response(
            False,
            str(e),
            error_type="DataProcessingError",
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


def create_parquet_file(
    s3_client, bucket_name: str, table_name: str, data: List[Dict]
) -> Dict:
    """
    Create a parquet file from input data and upload it to S3.
    """

    try:
        # Create DataFrame from input data
        df = pd.DataFrame(data)

        if df.empty:
            raise DataProcessingError(f"No data provided for table {table_name}")

        # Add metadata columns
        current_time = get_current_time().isoformat()
        df["created_at"] = current_time

        s3_key = "service_qualification/service_qualification.parquet"

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
                "original_columns": json.dumps(list(data[0].keys()) if data else []),
            },
        )

        s3_location = f"s3://{bucket_name}/{s3_key}"

        logger.info(
            f"Created parquet file for {table_name} with {len(df)} records at {s3_location}"
        )

        return create_response(
            True,
            f"Parquet file created successfully for table {table_name}",
            {
                "table_name": table_name,
                "record_count": len(df),
                "s3_location": s3_location,
                "s3_key": s3_key,
                "columns": list(df.columns),
                "created_at": current_time,
            },
        )

    except DataProcessingError:
        raise
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        logger.error(f"AWS S3 error ({error_code}): {error_message}")
        raise S3OperationError(f"S3 operation failed: {error_message}")
    except Exception as e:
        logger.error(f"Error creating parquet file for {table_name}: {str(e)}")
        raise DataProcessingError(f"Failed to create parquet file: {str(e)}")
