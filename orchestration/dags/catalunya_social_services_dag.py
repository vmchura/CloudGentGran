"""
Catalunya Social Services Pipeline - Airflow Orchestrator
=========================================================
Orchestrates Lambda functions for data extraction and transformation.
Airflow handles scheduling and coordination, Lambda handles processing.

Local environment uses mocked functions, dev/prod use actual Lambda functions.
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
ENVIRONMENT = Variable.get("environment", default_var="local")

# Environment-specific settings
ENV_CONFIG = {
    "local": {
        "use_lambda": False,  # Use mocked functions
        "schedule": timedelta(hours=2),  # More frequent for testing
        "timeout_minutes": 5,
        "bucket_name": "catalunya-data-local",
        "endpoint_url": "http://localstack:4566"  # LocalStack S3
    },
    "dev": {
        "use_lambda": True,  # Use actual Lambda functions
        "api_extractor_function": "catalunya-dev-social_services",
        "transformer_function": "catalunya-dev-social-services-transformer",
        "schedule": "0 23 * * 1",  # Monday 23:00
        "timeout_minutes": 15,
        "bucket_name": "catalunya-data-dev"
    },
    "prod": {
        "use_lambda": True,  # Use actual Lambda functions
        "api_extractor_function": "catalunya-prod-social_services",
        "transformer_function": "catalunya-prod-social-services-transformer",
        "schedule": "0 23 * * 5",  # Friday 23:00
        "timeout_minutes": 20,
        "bucket_name": "catalunya-data-prod"
    }
}

config = ENV_CONFIG.get(ENVIRONMENT, ENV_CONFIG["local"])

# =============================================================================
# LOCAL ENVIRONMENT - MOCKED FUNCTIONS
# =============================================================================

def mock_api_extractor(**context):
    """
    Mock API extractor for local development.
    Simulates Lambda response without actually calling Catalunya API.
    """
    logger.info("🔧 Running MOCK API extractor for local development")

    # Simulate processing time
    import time
    time.sleep(2)

    # Mock successful extraction response (matches real Lambda response format)
    mock_response = {
        'success': True,
        'message': 'Successfully processed 3 blocks with 2847 total records',
        'data': {
            'bucket': config.get('bucket_name', 'catalunya-data-local'),
            'semantic_identifier': 'social_services',
            'downloaded_date': datetime.utcnow().strftime('%Y%m%d'),
            'file_count': 3,
            'total_records': 2847,
            's3_keys': [
                'landing/social_services/downloaded_date=20250829/00000000.json',
                'landing/social_services/downloaded_date=20250829/00001000.json',
                'landing/social_services/downloaded_date=20250829/00002000.json'
            ],
            'source_prefix': f"landing/social_services/downloaded_date={datetime.utcnow().strftime('%Y%m%d')}/",
            'extraction_completed_at': datetime.utcnow().isoformat(),
            'next_step': 'trigger_transformer',
            'transformer_payload': {
                'bucket_name': config.get('bucket_name', 'catalunya-data-local'),
                'semantic_identifier': 'social_services',
                'downloaded_date': datetime.utcnow().strftime('%Y%m%d'),
                'file_count': 3,
                'total_records': 2847,
                'source_prefix': f"landing/social_services/downloaded_date={datetime.utcnow().strftime('%Y%m%d')}/",
                'extraction_timestamp': datetime.utcnow().isoformat()
            }
        },
        'timestamp': datetime.utcnow().isoformat(),
        'extractor': 'mock-social-services-api-extractor'
    }

    logger.info("✅ Mock extraction completed successfully")
    logger.info(f"   - Mock files created: {mock_response['data']['file_count']}")
    logger.info(f"   - Mock total records: {mock_response['data']['total_records']}")

    return mock_response

def mock_transformer(**context):
    """
    Mock transformer for local development.
    Simulates transformer Lambda response.
    """
    logger.info("🔧 Running MOCK transformer for local development")

    # Get the mock extraction data from previous task
    extraction_data = context['task_instance'].xcom_pull(key='transformer_payload')

    # Simulate processing time
    import time
    time.sleep(3)

    # Mock successful transformation response
    mock_response = {
        'success': True,
        'message': 'Successfully transformed 2847 records to staging layer',
        'data': {
            'input_records': extraction_data.get('total_records', 2847),
            'output_records': 2847,  # Assume no filtering in mock
            'staging_files_created': 1,
            'staging_prefix': f"staging/social_services/processed_date={datetime.utcnow().strftime('%Y%m%d')}/",
            'transformation_completed_at': datetime.utcnow().isoformat()
        },
        'timestamp': datetime.utcnow().isoformat(),
        'transformer': 'mock-social-services-transformer'
    }

    logger.info("✅ Mock transformation completed successfully")
    logger.info(f"   - Mock records processed: {mock_response['data']['input_records']}")

    return mock_response

# =============================================================================
# RESPONSE PARSING FUNCTIONS (WORKS FOR BOTH REAL AND MOCK)
# =============================================================================

def parse_lambda_response(**context) -> Dict[str, Any]:
    """
    Parse Lambda extractor response and prepare for next steps.
    Works with both real Lambda responses and mock responses.
    """
    task_instance = context['task_instance']

    if config['use_lambda']:
        # Real Lambda response
        lambda_response = task_instance.xcom_pull(task_ids='invoke_api_extractor')
        logger.info(f"Received Lambda response: {lambda_response}")

        # Parse Lambda response (might be wrapped)
        if isinstance(lambda_response, dict):
            response_body = lambda_response
        else:
            response_body = json.loads(lambda_response.get('Payload', '{}'))
    else:
        # Mock response
        response_body = task_instance.xcom_pull(task_ids='mock_api_extractor')
        logger.info(f"Received mock response: {response_body}")

    # Check if extraction was successful
    if not response_body.get('success', False):
        error_msg = response_body.get('message', 'Unknown extraction error')
        raise AirflowException(f"API extraction failed: {error_msg}")

    # Extract coordination data
    extraction_data = response_body.get('data', {})

    # Log extraction results for monitoring
    logger.info(f"✅ Extraction completed successfully:")
    logger.info(f"   - Files created: {extraction_data.get('file_count', 0)}")
    logger.info(f"   - Total records: {extraction_data.get('total_records', 0)}")
    logger.info(f"   - Source prefix: {extraction_data.get('source_prefix', 'N/A')}")

    # Prepare payload for transformer
    transformer_payload = extraction_data.get('transformer_payload', {})

    # Store for next task
    task_instance.xcom_push(key='transformer_payload', value=transformer_payload)
    task_instance.xcom_push(key='extraction_metadata', value=extraction_data)

    return extraction_data

def check_extraction_results(**context) -> str:
    """
    Validate extraction results and decide next steps.
    Pure coordination logic - no heavy processing.
    """
    task_instance = context['task_instance']
    extraction_data = task_instance.xcom_pull(key='extraction_metadata')

    # Business rules for validation
    min_expected_records = 100 if config['use_lambda'] else 50  # Lower threshold for mock
    file_count = extraction_data.get('file_count', 0)
    total_records = extraction_data.get('total_records', 0)

    logger.info(f"🔍 Validating extraction results:")
    logger.info(f"   - File count: {file_count}")
    logger.info(f"   - Record count: {total_records}")
    logger.info(f"   - Minimum expected: {min_expected_records}")
    logger.info(f"   - Environment: {ENVIRONMENT} ({'mock' if not config['use_lambda'] else 'real'})")

    # Validation checks
    if file_count == 0:
        raise AirflowException("No files were created during extraction")

    if total_records < min_expected_records:
        logger.warning(f"⚠️  Low record count: {total_records} < {min_expected_records}")
        # Don't fail, but log warning for investigation

    logger.info("✅ Extraction validation passed")
    return "validation_passed"

def trigger_dbt_workflow(**context):
    """
    Lightweight trigger for DBT workflow.
    Could invoke another DAG or run DBT commands.
    """
    logger.info("🚀 Triggering DBT transformations...")

    # Get extraction metadata
    extraction_data = context['task_instance'].xcom_pull(key='extraction_metadata')

    if config['use_lambda']:
        logger.info(f"DBT should process data from: {extraction_data.get('source_prefix')}")
    else:
        logger.info("DBT would process mock data (skipped in local environment)")

    # For now, just log - integrate with existing DBT DAG later
    return "dbt_triggered"

# =============================================================================
# DAG DEFINITION
# =============================================================================

dag = DAG(
    'catalunya_social_services_pipeline_orchestrator',
    default_args={
        'owner': 'catalunya-data-team',
        'depends_on_past': False,
        'start_date': datetime(2024, 1, 1),
        'email_on_failure': True,
        'email_on_retry': False,
        'retries': 2,
        'retry_delay': timedelta(minutes=5),
        'execution_timeout': timedelta(minutes=config['timeout_minutes'])
    },
    description=f'Catalunya Social Services Pipeline Orchestrator - {ENVIRONMENT} environment',
    schedule=config['schedule'],
    catchup=False,
    max_active_runs=1,
    tags=['catalunya', 'social-services', 'orchestrator', f'env:{ENVIRONMENT}']
)

# =============================================================================
# TASK CREATION - ENVIRONMENT AWARE
# =============================================================================

if config['use_lambda']:
    # REAL LAMBDA ENVIRONMENT (dev/prod)
    logger.info(f"Creating Lambda tasks for {ENVIRONMENT} environment")

    # Task 1: Invoke API Extractor Lambda
    invoke_api_extractor = LambdaInvokeFunctionOperator(
        task_id='invoke_api_extractor',
        function_name=config['api_extractor_function'],
        invocation_type='RequestResponse',  # Synchronous
        payload=json.dumps({
            'source': 'airflow.orchestrator',
            'environment': ENVIRONMENT,
            'trigger_time': '{{ ts }}',
            'dag_run_id': '{{ dag_run.run_id }}',
            'task_instance_key_str': '{{ task_instance_key_str }}'
        }),
        dag=dag
    )

    # Task 4: Invoke Transformer Lambda
    invoke_transformer = LambdaInvokeFunctionOperator(
        task_id='invoke_transformer',
        function_name=config['transformer_function'],
        invocation_type='RequestResponse',
        payload="""{{ task_instance.xcom_pull(key='transformer_payload') | tojson }}""",
        dag=dag
    )

else:
    # LOCAL/MOCK ENVIRONMENT
    logger.info(f"Creating mock tasks for {ENVIRONMENT} environment")

    # Task 1: Mock API Extractor
    invoke_api_extractor = PythonOperator(
        task_id='mock_api_extractor',
        python_callable=mock_api_extractor,
        dag=dag
    )

    # Task 4: Mock Transformer
    invoke_transformer = PythonOperator(
        task_id='mock_transformer',
        python_callable=mock_transformer,
        dag=dag
    )

# Common tasks for all environments
parse_response = PythonOperator(
    task_id='parse_extraction_response',
    python_callable=parse_lambda_response,
    dag=dag
)

validate_results = PythonOperator(
    task_id='validate_extraction_results',
    python_callable=check_extraction_results,
    dag=dag
)

trigger_dbt = PythonOperator(
    task_id='trigger_dbt_workflow',
    python_callable=trigger_dbt_workflow,
    dag=dag
)

# Task Dependencies - Same flow regardless of environment
invoke_api_extractor >> parse_response >> validate_results >> invoke_transformer >> trigger_dbt