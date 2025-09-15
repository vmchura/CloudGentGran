"""
Catalog Initializer DAG
=======================
Orchestrates the execution of the Catalog Initializer Lambda functions,
which manages dimension tables stored as Parquet in S3 and registers them
in the AWS Glue Data Catalog.

Environment Configuration:
- local: Triggers LocalStack-deployed Lambdas (via CDK)
- dev:   Triggers the AWS Lambdas deployed in the development account
- prod:  Triggers the AWS Lambdas deployed in the production account

Details:
- Parallel execution of Service Type and Municipals catalog initializers
- Each pipeline creates payloads, invokes Lambda functions, and validates results
- Both initializers write parquet files directly to the catalog bucket
- Is disabled by default and triggered manually
Last updated: 2025-09-11
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

logger = logging.getLogger(__name__)

# Environment configuration
ENVIRONMENT = Variable.get("environment")

# Environment-specific settings
ENV_CONFIG = {
    "local": {
        "aws_conn_id": "localstack_default",
        "service_type_initializer_function": "catalunya-dev-service-type-catalog",
        "service_qualification_initializer_function": "catalunya-dev-service-qualification-catalog",
        "municipals_initializer_function": "catalunya-dev-municipals-catalog",
        "timeout_minutes": 10,
        "bucket_name": "catalunya-catalog-dev",
        "retry_attempts": 1,
        "retry_delay": timedelta(minutes=2)
    },
    "development": {
        "aws_conn_id": "aws_cross_account_role",
        "service_type_initializer_function": "catalunya-dev-service-type-catalog",
        "service_qualification_initializer_function": "catalunya-dev-service-qualification-catalog",
        "municipals_initializer_function": "catalunya-dev-municipals-catalog",
        "timeout_minutes": 15,
        "bucket_name": "catalunya-catalog-dev",
        "retry_attempts": 2,
        "retry_delay": timedelta(minutes=5)
    },
    "production": {
        "aws_conn_id": "aws_lambda_role_conn",
        "service_type_initializer_function": "catalunya-prod-service-type-catalog",
        "service_qualification_initializer_function": "catalunya-prod-service-qualification-catalog",
        "municipals_initializer_function": "catalunya-prod-municipals-catalog",
        "timeout_minutes": 20,
        "bucket_name": "catalunya-catalog-prod",
        "retry_attempts": 2,
        "retry_delay": timedelta(minutes=5)
    }
}

config = ENV_CONFIG.get(ENVIRONMENT, ENV_CONFIG["local"])

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_service_type_payload(**context):
    """
    Create the payload for the service type catalog initializer Lambda function.
    """

    payload = {
        'source': 'airflow.catalog_initializer',
        'environment': ENVIRONMENT,
        'trigger_time': context.get('ts'),
        'dag_run_id': context.get('dag_run').run_id if context.get('dag_run') else None,
        'task_instance_key_str': context.get('task_instance_key_str'),
        'bucket_name': config['bucket_name'],
        'table_name': 'service_type'
    }

    logger.info(f"Created payload for service type catalog initializer: {json.dumps(payload, indent=2, default=str)}")
    return json.dumps(payload)

def create_service_qualification_payload(**context):
    """
    Create the payload for the service qualification catalog initializer Lambda function.
    """

    payload = {
        'source': 'airflow.catalog_initializer',
        'environment': ENVIRONMENT,
        'trigger_time': context.get('ts'),
        'dag_run_id': context.get('dag_run').run_id if context.get('dag_run') else None,
        'task_instance_key_str': context.get('task_instance_key_str'),
        'bucket_name': config['bucket_name'],
        'table_name': 'service_qualification'
    }

    logger.info(f"Created payload for service type catalog initializer: {json.dumps(payload, indent=2, default=str)}")
    return json.dumps(payload)

def create_municipals_payload(**context):
    """
    Create the payload for the municipals catalog initializer Lambda function.
    """

    payload = {
        'source': 'airflow.catalog_initializer',
        'environment': ENVIRONMENT,
        'trigger_time': context.get('ts'),
        'dag_run_id': context.get('dag_run').run_id if context.get('dag_run') else None,
        'task_instance_key_str': context.get('task_instance_key_str'),
        'bucket_name': config['bucket_name'],
        'table_name': 'municipals'
    }

    logger.info(f"Created payload for municipals catalog initializer: {json.dumps(payload, indent=2, default=str)}")
    return json.dumps(payload)

# =============================================================================
# RESPONSE PARSING FUNCTIONS
# =============================================================================

def parse_service_type_response(**context) -> Dict[str, Any]:
    """
    Parse Service Type Catalog Initializer Lambda response and validate execution.
    """
    task_instance = context['task_instance']

    # Get the Lambda response from the invoke task
    lambda_response = task_instance.xcom_pull(task_ids='invoke_service_type_initializer')
    logger.info(f"Raw Service Type Lambda response received: {type(lambda_response)}")

    # Parse Lambda response - handle different response formats
    if lambda_response is None:
        logger.error("Lambda response is None - this means the invoke_service_type_initializer task didn't run or failed")
        raise AirflowException("No Lambda response found - previous task may have failed")
    elif isinstance(lambda_response, dict):
        # Direct response dict
        response_body = lambda_response
        logger.info(f"Using direct response dict")
    elif isinstance(lambda_response, str):
        try:
            response_body = json.loads(lambda_response)
            logger.info(f"Parsed JSON string response")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise AirflowException(f"Invalid JSON response from Lambda: {lambda_response}")
    elif hasattr(lambda_response, 'get'):
        # Response with Payload
        payload = lambda_response.get('Payload')
        if payload:
            try:
                response_body = json.loads(payload) if isinstance(payload, str) else payload
                logger.info(f"Parsed payload response")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse payload: {e}")
                raise AirflowException(f"Invalid JSON payload from Lambda: {payload}")
        else:
            response_body = lambda_response
            logger.info(f"Using full response without payload")
    else:
        logger.error(f"Unexpected response type: {type(lambda_response)}")
        raise AirflowException(f"Unexpected Lambda response format: {type(lambda_response)}")

    logger.info(f"Parsed response body: {json.dumps(response_body, indent=2, default=str)}")

    # Check for Lambda execution errors (statusCode from the Lambda response)
    status_code = response_body.get('statusCode', 200)
    if status_code != 200:
        error_body = response_body.get('body', 'Unknown error')
        if isinstance(error_body, str):
            try:
                error_data = json.loads(error_body)
                error_msg = error_data.get('error', error_body)
            except json.JSONDecodeError:
                error_msg = error_body
        else:
            error_msg = str(error_body)

        logger.error(f"Service Type Catalog Initializer Lambda failed with status {status_code}: {error_msg}")
        raise AirflowException(f"Service type catalog initialization failed: {error_msg}")

    # Parse successful response body
    body = response_body.get('body', '{}')
    if isinstance(body, str):
        try:
            catalog_data = json.loads(body)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse response body: {e}")
            raise AirflowException(f"Invalid JSON in response body: {body}")
    else:
        catalog_data = body

    # Enhanced logging for monitoring and debugging
    logger.info(f"✅ Service Type catalog initialization completed successfully:")
    logger.info(f"   - Environment: {ENVIRONMENT}")
    logger.info(f"   - Function: {config['service_type_initializer_function']}")
    logger.info(f"   - Table name: {catalog_data.get('table_name', 'N/A')}")
    logger.info(f"   - Records processed: {catalog_data.get('record_count', 'N/A')}")
    logger.info(f"   - S3 location: {catalog_data.get('s3_location', 'N/A')}")
    logger.info(f"   - Created at: {catalog_data.get('created_at', 'N/A')}")

    # Store catalog data for potential downstream tasks
    task_instance.xcom_push(key='service_type_metadata', value=catalog_data)

    return catalog_data

def parse_service_qualification_response(**context) -> Dict[str, Any]:
    """
    Parse Service Qualification Catalog Initializer Lambda response and validate execution.
    """
    task_instance = context['task_instance']

    # Get the Lambda response from the invoke task
    lambda_response = task_instance.xcom_pull(task_ids='invoke_service_qualification_initializer')
    logger.info(f"Raw Service Qualification Lambda response received: {type(lambda_response)}")

    # Parse Lambda response - handle different response formats
    if lambda_response is None:
        logger.error("Lambda response is None - this means the invoke_service_qualification_initializer task didn't run or failed")
        raise AirflowException("No Lambda response found - previous task may have failed")
    elif isinstance(lambda_response, dict):
        # Direct response dict
        response_body = lambda_response
        logger.info(f"Using direct response dict")
    elif isinstance(lambda_response, str):
        try:
            response_body = json.loads(lambda_response)
            logger.info(f"Parsed JSON string response")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise AirflowException(f"Invalid JSON response from Lambda: {lambda_response}")
    elif hasattr(lambda_response, 'get'):
        # Response with Payload
        payload = lambda_response.get('Payload')
        if payload:
            try:
                response_body = json.loads(payload) if isinstance(payload, str) else payload
                logger.info(f"Parsed payload response")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse payload: {e}")
                raise AirflowException(f"Invalid JSON payload from Lambda: {payload}")
        else:
            response_body = lambda_response
            logger.info(f"Using full response without payload")
    else:
        logger.error(f"Unexpected response type: {type(lambda_response)}")
        raise AirflowException(f"Unexpected Lambda response format: {type(lambda_response)}")

    logger.info(f"Parsed response body: {json.dumps(response_body, indent=2, default=str)}")

    # Check for Lambda execution errors (statusCode from the Lambda response)
    status_code = response_body.get('statusCode', 200)
    if status_code != 200:
        error_body = response_body.get('body', 'Unknown error')
        if isinstance(error_body, str):
            try:
                error_data = json.loads(error_body)
                error_msg = error_data.get('error', error_body)
            except json.JSONDecodeError:
                error_msg = error_body
        else:
            error_msg = str(error_body)

        logger.error(f"Service Type Catalog Initializer Lambda failed with status {status_code}: {error_msg}")
        raise AirflowException(f"Service type catalog initialization failed: {error_msg}")

    # Parse successful response body
    body = response_body.get('body', '{}')
    if isinstance(body, str):
        try:
            catalog_data = json.loads(body)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse response body: {e}")
            raise AirflowException(f"Invalid JSON in response body: {body}")
    else:
        catalog_data = body

    # Enhanced logging for monitoring and debugging
    logger.info(f"✅ Service Qualification catalog initialization completed successfully:")
    logger.info(f"   - Environment: {ENVIRONMENT}")
    logger.info(f"   - Function: {config['service_qualification_initializer_function']}")
    logger.info(f"   - Table name: {catalog_data.get('table_name', 'N/A')}")
    logger.info(f"   - Records processed: {catalog_data.get('record_count', 'N/A')}")
    logger.info(f"   - S3 location: {catalog_data.get('s3_location', 'N/A')}")
    logger.info(f"   - Created at: {catalog_data.get('created_at', 'N/A')}")

    # Store catalog data for potential downstream tasks
    task_instance.xcom_push(key='service_qualification_metadata', value=catalog_data)

    return catalog_data

def parse_municipals_response(**context) -> Dict[str, Any]:
    """
    Parse Municipals Catalog Initializer Lambda response and validate execution.
    """
    task_instance = context['task_instance']

    # Get the Lambda response from the invoke task
    lambda_response = task_instance.xcom_pull(task_ids='invoke_municipals_initializer')
    logger.info(f"Raw Municipals Lambda response received: {type(lambda_response)}")

    # Parse Lambda response - handle different response formats
    if lambda_response is None:
        logger.error("Lambda response is None - this means the invoke_municipals_initializer task didn't run or failed")
        raise AirflowException("No Lambda response found - previous task may have failed")
    elif isinstance(lambda_response, dict):
        # Direct response dict
        response_body = lambda_response
        logger.info(f"Using direct response dict")
    elif isinstance(lambda_response, str):
        try:
            response_body = json.loads(lambda_response)
            logger.info(f"Parsed JSON string response")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise AirflowException(f"Invalid JSON response from Lambda: {lambda_response}")
    elif hasattr(lambda_response, 'get'):
        # Response with Payload
        payload = lambda_response.get('Payload')
        if payload:
            try:
                response_body = json.loads(payload) if isinstance(payload, str) else payload
                logger.info(f"Parsed payload response")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse payload: {e}")
                raise AirflowException(f"Invalid JSON payload from Lambda: {payload}")
        else:
            response_body = lambda_response
            logger.info(f"Using full response without payload")
    else:
        logger.error(f"Unexpected response type: {type(lambda_response)}")
        raise AirflowException(f"Unexpected Lambda response format: {type(lambda_response)}")

    logger.info(f"Parsed response body: {json.dumps(response_body, indent=2, default=str)}")

    # Validate successful execution based on municipals lambda response format
    if not response_body.get('success', False):
        error_msg = response_body.get('message', 'Unknown municipals extraction error')
        logger.error(f"Municipals extraction failed: {error_msg}")
        raise AirflowException(f"Municipals catalog extraction failed: {error_msg}")

    # Extract municipals data
    municipals_data = response_body.get('data', {})

    # Enhanced logging for monitoring and debugging
    logger.info(f"✅ Municipals catalog initialization completed successfully:")
    logger.info(f"   - Environment: {ENVIRONMENT}")
    logger.info(f"   - Function: {config['municipals_initializer_function']}")
    logger.info(f"   - Total records: {municipals_data.get('total_records', 'N/A')}")
    logger.info(f"   - S3 key: {municipals_data.get('s3_key', 'N/A')}")
    logger.info(f"   - Bucket: {municipals_data.get('bucket', 'N/A')}")
    logger.info(f"   - Extraction completed at: {municipals_data.get('extraction_completed_at', 'N/A')}")

    # Store catalog data for potential downstream tasks
    task_instance.xcom_push(key='municipals_metadata', value=municipals_data)

    return municipals_data

def validate_service_type_results(**context) -> str:
    """
    Validate service type catalog initialization results and apply business rules.
    Pure coordination logic - no heavy processing.
    """
    task_instance = context['task_instance']

    # Get catalog metadata from previous task
    catalog_data = task_instance.xcom_pull(task_ids='parse_service_type_response', key='service_type_metadata')

    if not catalog_data:
        logger.error("service_type catalog_data is None or empty")
        # Try alternative approach - get the return value of parse_service_type_response
        catalog_data = task_instance.xcom_pull(task_ids='parse_service_type_response')
        logger.info(f"Trying return value instead: {catalog_data}")

        if not catalog_data:
            raise AirflowException("No service type catalog metadata found - previous task may have failed")

    # Business validation rules
    table_name = catalog_data.get('table_name', 'unknown')
    record_count = catalog_data.get('record_count', 0)
    s3_location = catalog_data.get('s3_location', '')
    created_at = catalog_data.get('created_at', '')

    logger.info(f"🔍 Validating service type catalog initialization results:")
    logger.info(f"   - Table name: {table_name}")
    logger.info(f"   - Record count: {record_count}")
    logger.info(f"   - S3 location: {s3_location}")
    logger.info(f"   - Created at: {created_at}")

    # Critical validation checks
    if not table_name or table_name == 'unknown':
        raise AirflowException(f"Invalid table name: {table_name}")

    if record_count <= 0:
        raise AirflowException(f"No records were processed (record_count: {record_count})")

    if not s3_location or not s3_location.startswith('s3://'):
        raise AirflowException(f"Invalid S3 location: {s3_location}")

    if not created_at:
        logger.warning("⚠️  No creation timestamp found in response")

    logger.info("✅ Service type catalog initialization validation passed")
    return "service_type_validation_passed"

def validate_service_qualification_results(**context) -> str:
    """
    Validate service qualification catalog initialization results and apply business rules.
    Pure coordination logic - no heavy processing.
    """
    task_instance = context['task_instance']

    # Get catalog metadata from previous task
    catalog_data = task_instance.xcom_pull(task_ids='parse_service_qualification_response', key='service_qualification_metadata')

    if not catalog_data:
        logger.error("service_qualification catalog_data is None or empty")
        # Try alternative approach - get the return value of parse_service_qualification_response
        catalog_data = task_instance.xcom_pull(task_ids='parse_service_qualification_response')
        logger.info(f"Trying return value instead: {catalog_data}")

        if not catalog_data:
            raise AirflowException("No service type catalog metadata found - previous task may have failed")

    # Business validation rules
    table_name = catalog_data.get('table_name', 'unknown')
    record_count = catalog_data.get('record_count', 0)
    s3_location = catalog_data.get('s3_location', '')
    created_at = catalog_data.get('created_at', '')

    logger.info(f"🔍 Validating service type catalog initialization results:")
    logger.info(f"   - Table name: {table_name}")
    logger.info(f"   - Record count: {record_count}")
    logger.info(f"   - S3 location: {s3_location}")
    logger.info(f"   - Created at: {created_at}")

    # Critical validation checks
    if not table_name or table_name == 'unknown':
        raise AirflowException(f"Invalid table name: {table_name}")

    if record_count <= 0:
        raise AirflowException(f"No records were processed (record_count: {record_count})")

    if not s3_location or not s3_location.startswith('s3://'):
        raise AirflowException(f"Invalid S3 location: {s3_location}")

    if not created_at:
        logger.warning("⚠️  No creation timestamp found in response")

    logger.info("✅ Service type catalog initialization validation passed")
    return "service_qualification_validation_passed"

def validate_municipals_results(**context) -> str:
    """
    Validate municipals catalog initialization results and apply business rules.
    Pure coordination logic - no heavy processing.
    """
    task_instance = context['task_instance']

    # Get municipals metadata from previous task
    municipals_data = task_instance.xcom_pull(task_ids='parse_municipals_response', key='municipals_metadata')

    if not municipals_data:
        logger.error("municipals_data is None or empty")
        # Try alternative approach - get the return value of parse_municipals_response
        municipals_data = task_instance.xcom_pull(task_ids='parse_municipals_response')
        logger.info(f"Trying return value instead: {municipals_data}")

        if not municipals_data:
            raise AirflowException("No municipals metadata found - previous task may have failed")

    # Business validation rules
    total_records = municipals_data.get('total_records', 0)
    s3_key = municipals_data.get('s3_key', '')
    bucket = municipals_data.get('bucket', '')
    extraction_completed_at = municipals_data.get('extraction_completed_at', '')
    min_expected_records = 100  # Minimum expected for municipals data

    logger.info(f"🔍 Validating municipals catalog initialization results:")
    logger.info(f"   - Total records: {total_records}")
    logger.info(f"   - S3 key: {s3_key}")
    logger.info(f"   - Bucket: {bucket}")
    logger.info(f"   - Extraction completed at: {extraction_completed_at}")

    # Critical validation checks
    if total_records <= 0:
        raise AirflowException(f"No records were extracted (total_records: {total_records})")

    if not s3_key:
        raise AirflowException(f"No S3 key provided: {s3_key}")

    if not bucket:
        raise AirflowException(f"No bucket provided: {bucket}")

    # Warning checks (don't fail the pipeline)
    if total_records < min_expected_records:
        logger.warning(f"⚠️  Low record count detected for municipals: {total_records} < {min_expected_records}")
        logger.warning(f"   This may indicate an issue with the data source or extraction logic")
        # Continue processing but flag for investigation

    if not extraction_completed_at:
        logger.warning("⚠️  No extraction completion timestamp found in response")

    logger.info("✅ Municipals catalog initialization validation passed")
    return "municipals_validation_passed"

# =============================================================================
# DAG DEFINITION
# =============================================================================

dag = DAG(
    'catalunya_catalog_initializer',
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
    description=f'Catalunya Catalog Initializer - {ENVIRONMENT} environment',
    schedule=None,  # Manual trigger only - no scheduling
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=True,  # Disabled by default
    tags=['catalunya', 'catalog', 'initializer', 'manual', f'env:{ENVIRONMENT}']
)

# =============================================================================
# TASK CREATION - LOCALSTACK AND AWS COMPATIBLE
# =============================================================================

logger.info(f"🏗️  Creating catalog initializer tasks for {ENVIRONMENT} environment")
logger.info(f"   - AWS Connection ID: {config['aws_conn_id']}")
logger.info(f"   - Service Type Initializer function: {config['service_type_initializer_function']}")
logger.info(f"   - Service Qualification Initializer function: {config['service_qualification_initializer_function']}")
logger.info(f"   - Municipals Initializer function: {config['municipals_initializer_function']}")

# =============================================================================
# SERVICE TYPE CATALOG TASKS
# =============================================================================

# Task 1a: Create payload for Service Type Lambda invocation
create_service_type_payload_task = PythonOperator(
    task_id='create_service_type_payload',
    python_callable=create_service_type_payload,
    dag=dag
)

# Task 2a: Invoke Service Type Catalog Initializer Lambda
invoke_service_type_initializer = LambdaInvokeFunctionOperator(
    task_id='invoke_service_type_initializer',
    function_name=config['service_type_initializer_function'],
    aws_conn_id=config['aws_conn_id'],
    invocation_type='RequestResponse',  # Synchronous invocation
    payload='{{ task_instance.xcom_pull(task_ids="create_service_type_payload") }}',
    dag=dag
)

# Task 3a: Parse and validate service type catalog initializer response
parse_service_type_response = PythonOperator(
    task_id='parse_service_type_response',
    python_callable=parse_service_type_response,
    dag=dag
)

# Task 4a: Validate service type catalog initialization results
validate_service_type_results = PythonOperator(
    task_id='validate_service_type_results',
    python_callable=validate_service_type_results,
    dag=dag
)

# =============================================================================
# SERVICE QUALIFICATION CATALOG TASKS
# =============================================================================

# Task 1a: Create payload for Service Type Lambda invocation
create_service_qualification_payload_task = PythonOperator(
    task_id='create_service_qualification_payload',
    python_callable=create_service_qualification_payload,
    dag=dag
)

# Task 2a: Invoke Service Type Catalog Initializer Lambda
invoke_service_qualification_initializer = LambdaInvokeFunctionOperator(
    task_id='invoke_service_qualification_initializer',
    function_name=config['service_qualification_initializer_function'],
    aws_conn_id=config['aws_conn_id'],
    invocation_type='RequestResponse',  # Synchronous invocation
    payload='{{ task_instance.xcom_pull(task_ids="create_service_qualification_payload") }}',
    dag=dag
)

# Task 3a: Parse and validate service type catalog initializer response
parse_service_qualification_response = PythonOperator(
    task_id='parse_service_qualification_response',
    python_callable=parse_service_qualification_response,
    dag=dag
)

# Task 4a: Validate service type catalog initialization results
validate_service_qualification_results = PythonOperator(
    task_id='validate_service_qualification_results',
    python_callable=validate_service_qualification_results,
    dag=dag
)

# =============================================================================
# MUNICIPALS CATALOG TASKS
# =============================================================================

# Task 1b: Create payload for Municipals Lambda invocation
create_municipals_payload_task = PythonOperator(
    task_id='create_municipals_payload',
    python_callable=create_municipals_payload,
    dag=dag
)

# Task 2b: Invoke Municipals Catalog Initializer Lambda
invoke_municipals_initializer = LambdaInvokeFunctionOperator(
    task_id='invoke_municipals_initializer',
    function_name=config['municipals_initializer_function'],
    aws_conn_id=config['aws_conn_id'],
    invocation_type='RequestResponse',  # Synchronous invocation
    payload='{{ task_instance.xcom_pull(task_ids="create_municipals_payload") }}',
    dag=dag
)

# Task 3b: Parse and validate municipals catalog initializer response
parse_municipals_response = PythonOperator(
    task_id='parse_municipals_response',
    python_callable=parse_municipals_response,
    dag=dag
)

# Task 4b: Validate municipals catalog initialization results
validate_municipals_results = PythonOperator(
    task_id='validate_municipals_results',
    python_callable=validate_municipals_results,
    dag=dag
)

# =============================================================================
# TASK DEPENDENCIES
# =============================================================================

# Parallel execution of both catalog initializers
# Service Type pipeline
create_service_type_payload_task >> invoke_service_type_initializer >> parse_service_type_response >> validate_service_type_results

# Service Qualification pipeline
create_service_qualification_payload_task >> invoke_service_qualification_initializer >> parse_service_qualification_response >> validate_service_qualification_results

# Municipals pipeline
create_municipals_payload_task >> invoke_municipals_initializer >> parse_municipals_response >> validate_municipals_results