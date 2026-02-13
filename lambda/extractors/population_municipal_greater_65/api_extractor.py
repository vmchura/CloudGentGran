import json
import boto3
import urllib.request
import urllib.error
import logging
import time
from datetime import datetime, UTC
from typing import Dict, Any, List, Optional, Tuple
import os
import socket
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class PopulationExtractorError(Exception):
    """Base exception for population extractor errors"""

    pass


class ConfigurationError(PopulationExtractorError):
    """Raised when there's a configuration error"""

    pass


class APIError(PopulationExtractorError):
    """Raised when API requests fail"""

    pass


class S3OperationError(PopulationExtractorError):
    """Raised when S3 operations fail"""

    pass


class DataValidationError(PopulationExtractorError):
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


def validate_environment() -> Tuple[str, str]:
    """Validate required environment variables"""
    bucket_name = os.environ.get("BUCKET_NAME")
    semantic_identifier = os.environ.get("SEMANTIC_IDENTIFIER")

    missing_vars = []
    if not bucket_name:
        missing_vars.append("BUCKET_NAME")
    if not semantic_identifier:
        missing_vars.append("SEMANTIC_IDENTIFIER")

    if missing_vars:
        raise ConfigurationError(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )

    return bucket_name, semantic_identifier


def fetch_year_population_with_retry(
    url: str, year: str, max_retries: int = 3
) -> bytes:
    """Fetch population data for a specific year with retry logic"""
    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                return response.read()

        except urllib.error.HTTPError as e:
            if attempt >= max_retries:
                raise APIError(f"HTTP {e.code} error for year {year}: {e.reason}")

            sleep_time = 2 * (2 ** (attempt - 1))
            logger.warning(
                f"Year {year}: attempt {attempt}/{max_retries} failed "
                f"(HTTP {e.code}). Retrying in {sleep_time}s"
            )
            time.sleep(sleep_time)

        except urllib.error.URLError as e:
            if attempt >= max_retries:
                raise APIError(f"URL error for year {year}: {e.reason}")

            sleep_time = 2 * (2 ** (attempt - 1))
            logger.warning(
                f"Year {year}: attempt {attempt}/{max_retries} failed "
                f"(URLError). Retrying in {sleep_time}s"
            )
            time.sleep(sleep_time)

        except (socket.timeout, TimeoutError) as e:
            if attempt >= max_retries:
                raise APIError(f"Timeout error for year {year}: Request timed out")

            sleep_time = 2 * (2 ** (attempt - 1))
            logger.warning(
                f"Year {year}: attempt {attempt}/{max_retries} failed "
                f"(Timeout). Retrying in {sleep_time}s"
            )
            time.sleep(sleep_time)

        except ConnectionResetError as e:
            if attempt >= max_retries:
                raise APIError(f"Connection reset for year {year}")

            sleep_time = 2 * (2 ** (attempt - 1))
            logger.warning(
                f"Year {year}: attempt {attempt}/{max_retries} failed "
                f"(ConnectionReset). Retrying in {sleep_time}s"
            )
            time.sleep(sleep_time)


def fetch_href_base_url() -> Tuple[Optional[str], Optional[str]]:
    """Fetch the base URL for municipal population data"""
    try:
        with urllib.request.urlopen(
            "https://api.idescat.cat/taules/v2", timeout=30
        ) as url:
            try:
                response_data = json.load(url)
            except json.JSONDecodeError as e:
                raise APIError(f"Invalid JSON response from statistics API: {str(e)}")

            all_statistics = response_data.get("link", {}).get("item", [])
            if len(all_statistics) == 0:
                return None, "No metrics found"

            href_population_and_homes = next(
                (
                    entity["href"]
                    for entity in all_statistics
                    if "Cens de població i habitatges" == entity.get("label")
                ),
                None,
            )
            if href_population_and_homes is None:
                return None, "No metric of target population found"

        time.sleep(1)

        with urllib.request.urlopen(href_population_and_homes, timeout=30) as url:
            try:
                response_data = json.load(url)
            except json.JSONDecodeError as e:
                raise APIError(f"Invalid JSON response from nodes API: {str(e)}")

            all_nodes = response_data.get("link", {}).get("item", [])
            if len(all_nodes) == 0:
                return None, "No nodes found"

            href_sex_and_age_by_large_groups = next(
                (
                    single_node["href"]
                    for single_node in all_nodes
                    if single_node.get("label")
                    == "Població. Per sexe i edat en grans grups"
                ),
                None,
            )
            if href_sex_and_age_by_large_groups is None:
                return None, "No node of target population found"

        time.sleep(1)

        with urllib.request.urlopen(
            href_sex_and_age_by_large_groups, timeout=30
        ) as url:
            try:
                response_data = json.load(url)
            except json.JSONDecodeError as e:
                raise APIError(f"Invalid JSON response from tables API: {str(e)}")

            all_tables = response_data.get("link", {}).get("item", [])
            if len(all_tables) > 1:
                return None, "More than 1 table found"
            if len(all_tables) == 0:
                return None, "No table found"
            href_table_sex_and_age_by_large_groups = all_tables[0].get("href")
            if not href_table_sex_and_age_by_large_groups:
                return None, "No href found in table"

        time.sleep(1)

        with urllib.request.urlopen(
            href_table_sex_and_age_by_large_groups, timeout=30
        ) as url:
            try:
                response_data = json.load(url)
            except json.JSONDecodeError as e:
                raise APIError(f"Invalid JSON response from territories API: {str(e)}")

            all_territories = response_data.get("link", {}).get("item", [])
            if len(all_territories) == 0:
                return None, "No territories found from api"

            href_municipal_sex_and_age_by_large_groups = next(
                (
                    single_territory["href"]
                    for single_territory in all_territories
                    if single_territory.get("label") == "Per municipis"
                ),
                None,
            )

            if href_municipal_sex_and_age_by_large_groups is None:
                return None, "No territory target found from api"

        return href_municipal_sex_and_age_by_large_groups, None

    except urllib.error.HTTPError as e:
        raise APIError(f"HTTP {e.code} error fetching base URL: {e.reason}")
    except urllib.error.URLError as e:
        raise APIError(f"URL error fetching base URL: {e.reason}")
    except TimeoutError:
        raise APIError("Timeout error fetching base URL")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main Lambda handler function"""
    try:
        logger.info(f"Starting API extraction process at {datetime.now(UTC)}")

        # Validate environment variables
        bucket_name, semantic_identifier = validate_environment()

        href_municipal_sex_and_age_by_large_groups, error_url = fetch_href_base_url()

        if error_url is not None:
            raise DataValidationError(error_url)

        if href_municipal_sex_and_age_by_large_groups is None:
            raise DataValidationError("Error getting url base")

        time.sleep(1)

        # Fetch metadata for available years
        metadata_url = (
            href_municipal_sex_and_age_by_large_groups + "?SEX=TOTAL&AGE=Y_GE065,TOTAL"
        )
        try:
            with urllib.request.urlopen(metadata_url, timeout=30) as url:
                try:
                    metadata_years = json.load(url)
                except json.JSONDecodeError as e:
                    raise APIError(f"Invalid JSON response from metadata API: {str(e)}")
        except urllib.error.HTTPError as e:
            raise APIError(f"HTTP {e.code} error fetching metadata: {e.reason}")
        except urllib.error.URLError as e:
            raise APIError(f"URL error fetching metadata: {e.reason}")
        except TimeoutError:
            raise APIError("Timeout error fetching metadata")

        # Extract years from metadata
        try:
            all_years = metadata_years["dimension"]["YEAR"]["category"]["index"]
        except (KeyError, TypeError) as e:
            raise DataValidationError(f"Invalid metadata structure: {str(e)}")

        s3_keys: List[str] = []

        logger.info(f"Starting download for date")

        for single_year in all_years:
            logger.info(f"Attempt to download year {single_year}")
            time.sleep(3)
            url = (
                href_municipal_sex_and_age_by_large_groups
                + f"/data?SEX=TOTAL&AGE=Y_GE065,TOTAL&YEAR={single_year}"
            )

            try:
                raw_json_bytes = fetch_year_population_with_retry(url, single_year)
                raw_json_str = raw_json_bytes.decode("utf-8")

                try:
                    temporal_result = json.loads(raw_json_str)
                except json.JSONDecodeError as e:
                    raise DataValidationError(
                        f"Invalid JSON for year {single_year}: {str(e)}"
                    )

                if temporal_result.get("value"):
                    logger.info(
                        f"year {single_year}: Processing {len(temporal_result['value'])} records"
                    )
                    s3_key = upload_to_s3(
                        bucket_name, raw_json_bytes, semantic_identifier, single_year
                    )
                    s3_keys.append(s3_key)
                else:
                    logger.info(
                        f"No more data available. Finished at iteration {single_year}"
                    )
                    break
            except (APIError, DataValidationError, S3OperationError):
                raise
            except Exception as e:
                raise PopulationExtractorError(
                    f"Unexpected error processing year {single_year}: {str(e)}"
                )

        if len(all_years) != len(s3_keys):
            raise DataValidationError(
                f"Not all years downloaded. Expected {len(all_years)}, got {len(s3_keys)}"
            )

        logger.info(
            "Successfully completed extraction - returning metadata for Airflow coordination"
        )

        return create_response(
            True,
            f"Successfully processed {len(s3_keys)} blocks",
            {
                "bucket": bucket_name,
                "semantic_identifier": semantic_identifier,
                "extraction_completed_at": datetime.now(UTC).isoformat(),
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
    except PopulationExtractorError as e:
        logger.error(f"Extractor error: {str(e)}")
        return create_response(
            False, str(e), {"error_type": "PopulationExtractorError"}
        )
    except Exception as e:
        logger.error(f"Unexpected error in lambda_handler: {str(e)}")
        return create_response(
            False, "An unexpected error occurred", {"error_type": type(e).__name__}
        )


def upload_to_s3(
    bucket_name: str, json_data: bytes, semantic_identifier: str, year: str
) -> str:
    """Upload extracted data to S3 landing bucket"""
    try:
        s3_client = get_s3_client()

        s3_key = f"landing/{semantic_identifier}/{year}.json"

        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json_data,
            ContentType="application/json",
            Metadata={
                "extractor": "population-municipal-greater-65-api-extractor",
                "semantic_identifier": semantic_identifier,
                "year": year,
                "extraction_timestamp": datetime.now(UTC).isoformat(),
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
    """Create standardized Lambda response"""
    response: Dict[str, Any] = {
        "statusCode": 200 if success else 500,
        "success": success,
        "message": message,
        "timestamp": datetime.now(UTC).isoformat(),
        "extractor": "population-municipal-greater-65-api-extractor",
    }

    if data:
        response["data"] = data

    return response
