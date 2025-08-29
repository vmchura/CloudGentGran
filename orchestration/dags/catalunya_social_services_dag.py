"""
Catalunya Social Services Pipeline - Airflow Orchestrator
=========================================================
Orchestrates Lambda functions for data extraction and transformation.
Airflow handles scheduling and coordination, Lambda handles processing.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from airflow import DAG
from airflow.providers.amazon.aws.operators.lambda_function import LambdaInvokeFunctionOperator
from airflow.operators.python import PythonOperator
from airflow.models import Variable
from airflow.exceptions import AirflowException

logger = logging.getLogger(__name__)

# Environment configuration
ENVIRONMENT = Variable.get("environment", default_var="local")

# Environment-specific settings
ENV_CONFIG = {
    "local": {
        "api_extractor_function": "catalunya-local-social_services",
        "transformer_function": "catalunya-local-social-services-transformer",
        "schedule": timedelta(hours=2),  # More frequent for testing
        "timeout_minutes": 10
    },
    "dev": {
        "api_extractor_function": "catalunya-dev-social_services",
        "transformer_function": "catalunya-dev-social-services-transformer",
        "schedule": "0 23 * * 1",  # Monday 23:00
        "timeout_minutes": 15
    },
    "prod": {
        "api_extractor_function": "catalunya-prod-social_services",
        "transformer_function": "catalunya-prod-social-services-transformer",
        "schedule": "0 23 * * 5",  # Friday 23:00
        "timeout_minutes": 20
    }
}

config = ENV_CONFIG.get(ENVIRONMENT, ENV_CONFIG["local"])

def parse_lambda_response(**context) -> Dict[str, Any]:
    """
    Parse Lambda extractor response and prepare for next steps.
    Pure coordination logic - no heavy processing.
    """
    task_instance = context['task_instance']
    lambda_response = task_instance.xcom_pull(task_ids='invoke_api_extractor')

    logger.info(f"Received Lambda response: {lambda_response}")

    # Parse Lambda response
    if isinstance(lambda_response, dict):
        # Direct response from Lambda
        response_body = lambda_response
    else:
        # Response wrapped in AWS format
        response_body = json.loads(lambda_response.get('Payload', '{}'))

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
    min_expected_records = 100  # Configurable threshold
    file_count = extraction_data.get('file_count', 0)
    total_records = extraction_data.get('total_records', 0)

    logger.info(f"🔍 Validating extraction results:")
    logger.info(f"   - File count: {file_count}")
    logger.info(f"   - Record count: {total_records}")
    logger.info(f"   - Minimum expected: {min_expected_records}")

    # Validation checks
    if file_count == 0:
        raise AirflowException("No files were created during extraction")

    if total_records < min_expected_records:
        logger.warning(f"⚠️  Low record count: {total_records} < {min_expected_records}")
        # Don't fail, but log warning for investigation

    logger.info("✅ Extraction validation passed")
    return "validation_passed"

# DAG Definition
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

# Task 2: Parse Lambda Response (Pure Airflow coordination)
parse_response = PythonOperator(
    task_id='parse_extraction_response',
    python_callable=parse_lambda_response,
    dag=dag
)

# Task 3: Validate Results (Pure Airflow coordination)
validate_results = PythonOperator(
    task_id='validate_extraction_results',
    python_callable=check_extraction_results,
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

# Task 5: Trigger DBT (from existing DAG - lightweight coordination)
def trigger_dbt_workflow(**context):
    """
    Lightweight trigger for DBT workflow.
    Could invoke another DAG or run DBT commands.
    """
    logger.info("🚀 Triggering DBT transformations...")

    # Option A: Trigger another DAG
    # from airflow.operators.dagrun_operator import TriggerDagRunOperator

    # Option B: Simple coordination logic
    extraction_data = context['task_instance'].xcom_pull(key='extraction_metadata')
    logger.info(f"DBT should process data from: {extraction_data.get('source_prefix')}")

    # For now, just log - integrate with existing DBT DAG later
    return "dbt_triggered"

trigger_dbt = PythonOperator(
    task_id='trigger_dbt_workflow',
    python_callable=trigger_dbt_workflow,
    dag=dag
)

# Task Dependencies - Pure orchestration flow
invoke_api_extractor >> parse_response >> validate_results >> invoke_transformer >> trigger_dbt