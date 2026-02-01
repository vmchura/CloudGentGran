import json
import boto3
import urllib.request
import urllib.error
import logging
import time
from datetime import datetime, UTC
from typing import Dict, Any, List
import os
import socket

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_s3_client():
    endpoint_url = os.environ.get("AWS_ENDPOINT_URL")
    if endpoint_url:
        logger.info(f"Using S3 endpoint: {endpoint_url}")
        return boto3.client("s3", endpoint_url=endpoint_url)
    else:
        logger.info("Using default S3 endpoint")
        return boto3.client("s3")


def fetch_year_population_with_retry(url, year, max_retries=3):
    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(url) as response:
                return response.read()

        except (urllib.error.URLError, socket.timeout, ConnectionResetError) as e:
            if attempt >= max_retries:
                logger.warning(f"Year {year}: attempt {attempt}/{max_retries} failed ")
                raise

            sleep_time = 2 * (2 ** (attempt - 1))
            logger.warning(
                f"Year {year}: attempt {attempt}/{max_retries} failed "
                f"({type(e).__name__}). Retrying in {sleep_time}s"
            )
            time.sleep(sleep_time)


def fetch_href_base_url() -> (str, str):
    with urllib.request.urlopen("https://api.idescat.cat/taules/v2") as url:
        all_statistics = json.load(url)["link"]["item"]
        if len(all_statistics) == 0:
            return (None, "No metrics found")
        href_population_and_homes = next(
            (
                entity["href"]
                for entity in all_statistics
                if "Cens de població i habitatges" == entity["label"]
            ),
            None,
        )
        if href_population_and_homes is None:
            return (None, "No metric of target population found")

    time.sleep(1)

    with urllib.request.urlopen(href_population_and_homes) as url:
        all_nodes = json.load(url)["link"]["item"]
        if len(all_nodes) == 0:
            return (None, "No nodes found")

        href_sex_and_age_by_large_groups = next(
            (
                single_node["href"]
                for single_node in all_nodes
                if single_node["label"] == "Població. Per sexe i edat en grans grups"
            ),
            None,
        )
        if href_sex_and_age_by_large_groups is None:
            return (None, "No node of target population found")

    time.sleep(1)

    with urllib.request.urlopen(href_sex_and_age_by_large_groups) as url:
        all_tables = json.load(url)["link"]["item"]
        if len(all_tables) > 1:
            return (None, "More than 1 table found")
        if len(all_tables) == 0:
            return (None, "No table found")
        href_table_sex_and_age_by_large_groups = all_tables[0]["href"]

    time.sleep(1)

    with urllib.request.urlopen(href_table_sex_and_age_by_large_groups) as url:
        all_territories = json.load(url)["link"]["item"]
        if len(all_territories) == 0:
            return (None, "No territories found from api")

        href_municipal_sex_and_age_by_large_groups = next(
            (
                single_territory["href"]
                for single_territory in all_territories
                if single_territory["label"] == "Per municipis"
            ),
            None,
        )

        if href_municipal_sex_and_age_by_large_groups is None:
            return (None, "No territory target found from api")

    return href_municipal_sex_and_age_by_large_groups, None


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    try:
        logger.info(f"Starting API extraction process at {datetime.now(UTC)}")

        bucket_name = os.environ["BUCKET_NAME"]
        semantic_identifier = os.environ["SEMANTIC_IDENTIFIER"]

        href_municipal_sex_and_age_by_large_groups, error_url = fetch_href_base_url()

        if error_url is not None:
            return createResponse(False, error_url)

        if href_municipal_sex_and_age_by_large_groups is None:
            return createResponse(False, "Error getting url base")

        time.sleep(1)

        with urllib.request.urlopen(
            href_municipal_sex_and_age_by_large_groups + "?SEX=TOTAL&AGE=Y_GE065,TOTAL"
        ) as url:
            metadata_years = json.load(url)
            all_years = metadata_years["dimension"]["YEAR"]["category"]["index"]

        s3_keys = []

        logger.info(f"Starting download for date")

        for single_year in all_years:
            logger.info(f"Attempt to download year {single_year}")
            time.sleep(3)
            url = (
                href_municipal_sex_and_age_by_large_groups
                + f"/data?SEX=TOTAL&AGE=Y_GE065,TOTAL&YEAR={single_year}"
            )
            raw_json_bytes = fetch_year_population_with_retry(url, single_year)
            raw_json_str = raw_json_bytes.decode("utf-8")
            temporal_result = json.loads(raw_json_str)
            if temporal_result.get("value", None):
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

        if len(all_years) != len(s3_keys):
            return create_response(False, "Not all years downloaded")

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
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return create_response(False, f"Error: {str(e)}")


def upload_to_s3(
    bucket_name: str, json_data: bytes, semantic_identifier: str, year: str
) -> str:
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

    except Exception as e:
        logger.error(f"Failed to upload to S3: {str(e)}")
        raise


def create_response(
    success: bool, message: str, data: Dict[str, Any] = None
) -> Dict[str, Any]:
    response = {
        "statusCode": 200 if success else 500,
        "success": success,
        "message": message,
        "timestamp": datetime.now(UTC).isoformat(),
        "extractor": "population-municipal-greater-65-api-extractor",
    }

    if data:
        response["data"] = data

    return response

