"""
Catalunya Social Services Pipeline - Updated for Direct Lambda Orchestration
===========================================================================
Orchestrates Lambda functions for data extraction and transformation without EventBridge.
Updated to work with the current lambda implementations and correct payload structures.

Environment Configuration:
- local: Uses LocalStack with CDK-deployed Lambda functions
- dev: Uses actual AWS Lambda functions
- prod: Uses actual AWS Lambda functions
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Variable
from airflow.exceptions import AirflowException
from airflow.providers.amazon.aws.operators.lambda_function import LambdaInvokeFunctionOperator
from operators.dbt_athena_operator import DbtAthenaOperator

logger = logging.getLogger(__name__)

# Environment configuration
ENVIRONMENT = Variable.get("environment")

# Environment-specific settings
ENV_CONFIG = {
    "local": {
        "aws_conn_id": "localstack_default",
        "api_extractor_function": "catalunya-dev-social_services",
        "transformer_function": "catalunya-dev-social-services-transformer",
        "catalog_bucket": "catalunya-catalog-dev",
        "data_bucket": "catalunya-data-dev",
        "athena_database_name": "catalunya_data_dev",
        "schedule": timedelta(hours=2),  # More frequent for testing
        "timeout_minutes": 15,
        "retry_attempts": 1,
        "retry_delay": timedelta(minutes=2)
    },
    "dev": {
        "aws_conn_id": "aws_cross_account_role",
        "api_extractor_function": "catalunya-dev-social_services",
        "transformer_function": "catalunya-dev-social-services-transformer",
        "catalog_bucket": "catalunya-catalog-dev",
        "athena_database_name": "catalunya_data_dev",
        "data_bucket": "catalunya-data-dev",
        "schedule": "0 23 * * 1",  # Monday 23:00
        "timeout_minutes": 15,
        "retry_attempts": 2,
        "retry_delay": timedelta(minutes=5)
    },
    "prod": {
        "aws_conn_id": "aws_lambda_role_conn",
        "api_extractor_function": "catalunya-prod-social_services",
        "transformer_function": "catalunya-prod-social-services-transformer",
        "catalog_bucket": "catalunya-catalog-prod",
        "athena_database_name": "catalunya_data_prod",
        "data_bucket": "catalunya-data-prod",
        "schedule": "0 23 * * 5",  # Friday 23:00
        "timeout_minutes": 20,
        "retry_attempts": 2,
        "retry_delay": timedelta(minutes=5)
    }
}

config = ENV_CONFIG[ENVIRONMENT]

# =============================================================================
# PAYLOAD PREPARATION AND COORDINATION FUNCTIONS
# =============================================================================

def prepare_extractor_payload(**context) -> Dict[str, Any]:
    """
    Prepare the payload for the Python extractor lambda.
    The extractor expects standard lambda event format.
    """
    payload = {
        'source': 'airflow.orchestrator',
        'environment': ENVIRONMENT,
        'trigger_time': context['ts'],
        'dag_run_id': context['dag_run'].run_id,
        'task_instance_key_str': context['task_instance_key_str'],
        'bucket_name': config['data_bucket'],
        'execution_date': context['ds']
    }

    logger.info(f"Prepared extractor payload: {json.dumps(payload, indent=2, default=str)}")
    return payload

def parse_extraction_response(**context) -> Dict[str, Any]:
    """
    Parse Lambda extractor response and prepare coordination data for the transformer.
    """
    task_instance = context['task_instance']

    # Get the Lambda response from the invoke task
    lambda_response = task_instance.xcom_pull(task_ids='invoke_api_extractor')
    logger.info(f"Raw Lambda response received: {type(lambda_response)}")

    # Parse Lambda response - handle different response formats
    if lambda_response is None:
        logger.error("Lambda response is None - extractor task failed")
        raise AirflowException("No Lambda response found - extractor task may have failed")

    # Handle various response formats
    if isinstance(lambda_response, dict):
        response_body = lambda_response
    elif isinstance(lambda_response, str):
        try:
            response_body = json.loads(lambda_response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise AirflowException(f"Invalid JSON response from Lambda: {lambda_response}")
    elif hasattr(lambda_response, 'get'):
        payload = lambda_response.get('Payload')
        if payload:
            try:
                response_body = json.loads(payload) if isinstance(payload, str) else payload
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse payload: {e}")
                raise AirflowException(f"Invalid JSON payload from Lambda: {payload}")
        else:
            response_body = lambda_response
    else:
        logger.error(f"Unexpected response type: {type(lambda_response)}")
        raise AirflowException(f"Unexpected Lambda response format: {type(lambda_response)}")

    logger.info(f"Parsed response body: {json.dumps(response_body, indent=2, default=str)}")

    # Validate successful extraction
    if not response_body.get('success', False):
        error_msg = response_body.get('message', 'Unknown extraction error')
        logger.error(f"Lambda extraction failed: {error_msg}")
        raise AirflowException(f"API extraction failed: {error_msg}")

    # Extract coordination data
    extraction_data = response_body.get('data', {})

    # Enhanced logging
    logger.info(f"✅ Extraction completed successfully:")
    logger.info(f"   - Environment: {ENVIRONMENT}")
    logger.info(f"   - Function: {config['api_extractor_function']}")
    logger.info(f"   - Files created: {extraction_data.get('file_count', 'N/A')}")
    logger.info(f"   - Total records: {extraction_data.get('total_records', 'N/A')}")
    logger.info(f"   - Source prefix: {extraction_data.get('source_prefix', 'N/A')}")
    logger.info(f"   - Bucket: {extraction_data.get('bucket', config['data_bucket'])}")

    # Store extraction metadata for next tasks
    task_instance.xcom_push(key='extraction_metadata', value=extraction_data)

    return extraction_data

def prepare_transformer_payload(**context) -> Dict[str, Any]:
    """
    Prepare the payload for the Rust transformer lambda based on extraction results.
    The Rust transformer expects: downloaded_date, bucket_name, semantic_identifier
    """
    task_instance = context['task_instance']

    # Get extraction metadata
    extraction_data = task_instance.xcom_pull(task_ids='parse_extraction_response', key='extraction_metadata')

    if not extraction_data:
        extraction_data = task_instance.xcom_pull(task_ids='parse_extraction_response')

    if not extraction_data:
        raise AirflowException("No extraction metadata found - previous task may have failed")

    # Extract downloaded_date from the extraction data or derive from context
    downloaded_date = extraction_data.get('downloaded_date')
    if not downloaded_date:
        # Fall back to execution date in YYYYMMDD format
        downloaded_date = datetime.strptime(context['ds'], '%Y-%m-%d').strftime('%Y%m%d')

    # Prepare payload matching the Rust transformer's expected input structure
    transformer_payload = {
        'environment': ENVIRONMENT,
        'downloaded_date': downloaded_date,
        'bucket_name': config['data_bucket'],
        'athena_database_name': config['athena_database_name'],
        'semantic_identifier': 'social_services'
    }

    logger.info(f"Prepared transformer payload: {json.dumps(transformer_payload, indent=2)}")

    # Store payload for the lambda operator
    task_instance.xcom_push(key='transformer_payload', value=transformer_payload)

    return transformer_payload

def validate_extraction_results(**context) -> str:
    """
    Validate extraction results and apply business rules.
    """
    task_instance = context['task_instance']

    # Get extraction metadata
    extraction_data = task_instance.xcom_pull(task_ids='parse_extraction_response', key='extraction_metadata')

    if not extraction_data:
        extraction_data = task_instance.xcom_pull(task_ids='parse_extraction_response')

    if not extraction_data:
        raise AirflowException("No extraction metadata found for validation")

    # Business validation rules
    min_expected_records = 100  # Minimum expected for social services data
    file_count = extraction_data.get('file_count', 0)
    total_records = extraction_data.get('total_records', 0)
    bucket_name = extraction_data.get('bucket', 'unknown')

    logger.info(f"🔍 Validating extraction results:")
    logger.info(f"   - Bucket: {bucket_name}")
    logger.info(f"   - File count: {file_count}")
    logger.info(f"   - Record count: {total_records}")
    logger.info(f"   - Minimum expected: {min_expected_records}")

    # Critical validation checks
    if file_count <= 0:
        raise AirflowException(f"No files were created during extraction (file_count: {file_count})")

    if total_records <= 0:
        raise AirflowException(f"No records were extracted (total_records: {total_records})")

    # Warning checks (don't fail the pipeline)
    if total_records < min_expected_records:
        logger.warning(f"⚠️  Low record count detected: {total_records} < {min_expected_records}")
        logger.warning(f"   This may indicate an issue with the data source or extraction logic")

    logger.info("✅ Extraction validation passed - proceeding to transformation")
    return "validation_passed"

def parse_transformation_response(**context) -> Dict[str, Any]:
    """
    Parse transformer Lambda response and prepare final coordination data.
    """
    task_instance = context['task_instance']

    # Get the transformer Lambda response
    transformer_response = task_instance.xcom_pull(task_ids='invoke_transformer')
    logger.info(f"Raw transformer response received: {type(transformer_response)}")

    # Parse transformer response using same logic as extractor
    if isinstance(transformer_response, dict):
        response_body = transformer_response
    elif isinstance(transformer_response, str):
        try:
            response_body = json.loads(transformer_response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse transformer JSON response: {e}")
            raise AirflowException(f"Invalid JSON response from transformer: {transformer_response}")
    elif hasattr(transformer_response, 'get'):
        payload = transformer_response.get('Payload')
        if payload:
            try:
                response_body = json.loads(payload) if isinstance(payload, str) else payload
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse transformer payload: {e}")
                raise AirflowException(f"Invalid JSON payload from transformer: {payload}")
        else:
            response_body = transformer_response
    else:
        logger.error(f"Unexpected transformer response type: {type(transformer_response)}")
        raise AirflowException(f"Unexpected transformer response format: {type(transformer_response)}")

    logger.info(f"Parsed transformer response: {json.dumps(response_body, indent=2, default=str)}")

    # Validate successful transformation
    if not response_body.get('success', False):
        error_msg = response_body.get('message', 'Unknown transformation error')
        logger.error(f"Lambda transformation failed: {error_msg}")
        raise AirflowException(f"Data transformation failed: {error_msg}")

    # Extract transformation results
    transformation_data = response_body.get('data', {})

    logger.info(f"✅ Transformation completed successfully:")
    logger.info(f"   - Environment: {ENVIRONMENT}")
    logger.info(f"   - Function: {config['transformer_function']}")
    logger.info(f"   - Input records: {transformation_data.get('raw_records', 'N/A')}")
    logger.info(f"   - Output records: {transformation_data.get('clean_records', 'N/A')}")
    logger.info(f"   - Files processed: {transformation_data.get('files_processed', 'N/A')}")
    logger.info(f"   - Target location: {transformation_data.get('target_location', 'N/A')}")

    # Store transformation metadata for potential downstream tasks
    task_instance.xcom_push(key='transformation_metadata', value=transformation_data)

    return transformation_data

def prepare_mart_payload(**context) -> str:
    """
    Trigger DBT workflow with staging data.
    Placeholder for future DBT integration.
    """
    task_instance = context['task_instance']

    # Get extraction metadata
    extraction_data = task_instance.xcom_pull(task_ids='parse_extraction_response', key='extraction_metadata')

    if not extraction_data:
        extraction_data = task_instance.xcom_pull(task_ids='parse_extraction_response')

    if not extraction_data:
        raise AirflowException("No extraction metadata found - previous task may have failed")

    # Extract downloaded_date from the extraction data or derive from context
    downloaded_date = extraction_data.get('downloaded_date')
    dbt_social_services_mart_parameters = {
        "downloaded_date": downloaded_date
    }

    return dbt_social_services_mart_parameters

# =============================================================================
# DAG DEFINITION
# =============================================================================

dag = DAG(
    'catalunya_social_services_pipeline',
    default_args={
        'owner': 'catalunya-data-team',
        'depends_on_past': False,
        'start_date': datetime(2024, 1, 1),
        'email_on_failure': True,
        'email_on_retry': False,
        'retries': config['retry_attempts'],
        'retry_delay': config['retry_delay'],
        'execution_timeout': timedelta(minutes=config['timeout_minutes'])
    },
    description=f'Catalunya Social Services Pipeline - {ENVIRONMENT})',
    schedule=config['schedule'],
    catchup=False,
    max_active_runs=1,
    tags=['catalunya', 'social-services', 'lambda-orchestration', 'athena-job', f'env:{ENVIRONMENT}']
)

# =============================================================================
# TASK CREATION
# =============================================================================

logger.info(f"🏗️  Creating pipeline tasks for {ENVIRONMENT} environment")
logger.info(f"   - AWS Connection ID: {config['aws_conn_id']}")
logger.info(f"   - Extractor function: {config['api_extractor_function']}")
logger.info(f"   - Transformer function: {config['transformer_function']}")

# Task 1: Prepare extractor payload
prepare_extractor_payload_task = PythonOperator(
    task_id='prepare_extractor_payload',
    python_callable=prepare_extractor_payload,
    dag=dag
)

# Task 2: Invoke API Extractor Lambda
invoke_api_extractor = LambdaInvokeFunctionOperator(
    task_id='invoke_api_extractor',
    function_name=config['api_extractor_function'],
    aws_conn_id=config['aws_conn_id'],
    invocation_type='RequestResponse',  # Synchronous invocation
    payload='{{ task_instance.xcom_pull(task_ids="prepare_extractor_payload") | tojson }}',
    dag=dag
)

# Task 3: Parse and validate extraction response
parse_extraction_response_task = PythonOperator(
    task_id='parse_extraction_response',
    python_callable=parse_extraction_response,
    dag=dag
)

# Task 4: Validate extraction results
validate_extraction_results_task = PythonOperator(
    task_id='validate_extraction_results',
    python_callable=validate_extraction_results,
    dag=dag
)

# Task 5: Prepare transformer payload
prepare_transformer_payload_task = PythonOperator(
    task_id='prepare_transformer_payload',
    python_callable=prepare_transformer_payload,
    dag=dag
)

# Task 6: Invoke Transformer Lambda
invoke_transformer = LambdaInvokeFunctionOperator(
    task_id='invoke_transformer',
    function_name=config['transformer_function'],
    aws_conn_id=config['aws_conn_id'],
    invocation_type='RequestResponse',
    payload='{{ task_instance.xcom_pull(task_ids="prepare_transformer_payload") | tojson }}',
    execution_timeout=timedelta(minutes=config.get('lambda_timeout_minutes', 15)),
    dag=dag
)

# Task 7: Parse transformation response
parse_transformation_response_task = PythonOperator(
    task_id='parse_transformation_response',
    python_callable=parse_transformation_response,
    dag=dag
)

# Task 8: Trigger DBT workflow
social_service_mart_model = DbtAthenaOperator(
    task_id='social_services_by_service_municipal',
    aws_conn_id='aws_cross_account_role',
    dbt_command='run',
    dbt_target=ENVIRONMENT,
    dbt_vars=prepare_mart_payload,
    select_models='social_services_by_service_municipal',
    dag=dag
)

# =============================================================================
# TASK DEPENDENCIES
# =============================================================================

# Linear pipeline flow with proper coordination
(prepare_extractor_payload_task >>
 invoke_api_extractor >>
 parse_extraction_response_task >>
 validate_extraction_results_task >>
 prepare_transformer_payload_task >>
 invoke_transformer >>
 parse_transformation_response_task >>
 social_service_mart_model)