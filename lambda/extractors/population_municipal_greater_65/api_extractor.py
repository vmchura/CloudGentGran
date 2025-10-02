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
        semantic_identifier = os.environ['SEMANTIC_IDENTIFIER']
        with urllib.request.urlopen("https://api.idescat.cat/taules/v2") as url:
            all_statistics = json.load(url)['link']['item']
            if len(all_statistics) == 0:
                return create_response(False, "No metrics found")
            href_population_and_homes = next(
                entity['href'] for entity in all_statistics if 'Cens de població i habitatges' == entity['label'], None)
            if href_population_and_homes is None:
                return create_response(False, "No metric of target population found")

        with urllib.request.urlopen(href_population_and_homes) as url:
            all_nodes = json.load(url)['link']['item']
            if len(all_nodes) == 0:
                return create_response(False, "No nodes found")

            href_sex_and_age_by_large_groups = next(single_node['href'] for single_node in all_nodes if
                                                    single_node['label'] == 'Població. Per sexe i edat en grans grups',
                                                    None)
            if href_sex_and_age_by_large_groups is None:
                return create_response(False, "No node of target population found")

        with urllib.request.urlopen(href_sex_and_age_by_large_groups) as url:
            all_tables = json.load(url)['link']['item']
            if len(all_tables) > 1:
                return create_response(False, "More than 1 table found")
            if len(all_tables) == 0:
                return create_response(False, "No table found")
            href_table_sex_and_age_by_large_groups = all_tables[0]['href']

        with urllib.request.urlopen(href_table_sex_and_age_by_large_groups) as url:
            all_territories = json.load(url)['link']['item']
            if len(all_territories) == 0:
                return create_response(False, "No territories found from api")

            href_municipal_sex_and_age_by_large_groups = next(
                single_territory['href'] for single_territory in all_territories if single_territory['label'] == 'Per municipis', None)

            if href_municipal_sex_and_age_by_large_groups is None:
                return create_response(False, "No territory target found from api")

        with urllib.request.urlopen(
                href_municipal_sex_and_age_by_large_groups + "?SEX=TOTAL&AGE=Y_GE065,TOTAL") as url:
            metadata_years = json.load(url)
            all_years = metadata_years['dimension']['YEAR']['category']['index']

        s3_keys = []

        logger.info(f"Starting download for date")

        for single_year in all_years[:10]:
            print(single_year)
            time.sleep(5)
            with urllib.request.urlopen(
                    href_municipal_sex_and_age_by_large_groups + f"/data?SEX=TOTAL&AGE=Y_GE065,TOTAL&YEAR={single_year}") as http_response:
                raw_json_bytes = http_response.read()
                raw_json_str = raw_json_bytes.decode("utf-8")
                temporal_result = json.loads(raw_json_str)
                if temporal_result.get('value', None):
                    logger.info(f"year {single_year}: Processing {len(temporal_result['value'])} records")
                    s3_key = upload_to_s3(bucket_name, raw_json_bytes, semantic_identifier, single_year)
                    s3_keys.append(s3_key)
                else:
                    logger.info(f"No more data available. Finished at iteration {single_year}")
                    break
        if len(all_years) != len(s3_keys):
            return create_response(False, "Not all years downloaded")


        # Return enhanced data for Airflow coordination
        logger.info("Successfully completed extraction - returning metadata for Airflow coordination")

        return create_response(True, f"Successfully processed {len(s3_keys)} blocks",
                               {
                                   'bucket': bucket_name,
                                   'semantic_identifier': semantic_identifier,
                                   'extraction_completed_at': datetime.utcnow().isoformat(),
                                   'transformer_payload': {
                                       'bucket_name': bucket_name,
                                       'semantic_identifier': semantic_identifier,
                                       's3_keys': s3_keys,
                                       'all_years': all_years,
                                   }
                               })

    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return create_response(False, f"Error: {str(e)}")


def upload_to_s3(bucket_name: str, json_data: bytes, semantic_identifier: str, year: str) -> str:
    """
    Upload extracted data to S3 landing bucket
    
    Args:
        bucket_name: S3 bucket name
        json_data: Raw JSON data as bytes
        semantic_identifier: Semantic identifier for the dataset
        year: year downloaded
    
    Returns:
        S3 key of the uploaded file
    """
    try:
        s3_client = get_s3_client()

        # Generate S3 key with partitioning by download date
        s3_key = f"landing/{semantic_identifier}/{year}.json"

        # Upload to S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json_data,
            ContentType='application/json',
            Metadata={
                'extractor': 'population-municipal-greater-65-api-extractor',
                'semantic_identifier': semantic_identifier,
                'year': year,
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
