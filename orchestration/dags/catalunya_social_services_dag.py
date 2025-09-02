"""
Catalunya Social Services Pipeline - LocalStack Integration
=========================================================
Orchestrates Lambda functions for data extraction and transformation.
Updated to work with LocalStack-deployed Lambda functions using CDK.

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

logger = logging.getLogger(__name__)

# Environment configuration
try:
    ENVIRONMENT = Variable.get("environment", default_var="local")
except Exception:
    # Fallback if Variable.get fails during DAG parsing
    ENVIRONMENT = "local"

# Environment-specific settings
ENV_CONFIG = {
    "local": {
        "use_localstack": True,
        "aws_conn_id": "localstack_default",
        "api_extractor_function": "catalunya-dev-social_services",
        "transformer_function": "catalunya-dev-social-services-transformer",
        "schedule": timedelta(hours=2),  # More frequent for testing
        "timeout_minutes": 10,
        "bucket_name": "catalunya-data-dev",
        "retry_attempts": 3,
        "retry_delay": timedelta(minutes=2)
    },
    "dev": {
        "use_localstack": False,
        "aws_conn_id": "aws_default",
        "api_extractor_function": "catalunya-dev-social_services",
        "transformer_function": "catalunya-dev-social-services-transformer",
        "schedule": "0 23 * * 1",  # Monday 23:00
        "timeout_minutes": 15,
        "bucket_name": "catalunya-data-dev",
        "retry_attempts": 2,
        "retry_delay": timedelta(minutes=5)
    },
    "prod": {
        "use_localstack": False,
        "aws_conn_id": "aws_default",
        "api_extractor_function": "catalunya-prod-social_services",
        "transformer_function": "catalunya-prod-social-services-transformer",
        "schedule": "0 23 * * 5",  # Friday 23:00
        "timeout_minutes": 20,
        "bucket_name": "catalunya-data-prod",
        "retry_attempts": 2,
        "retry_delay": timedelta(minutes=5)
    }
}

config = ENV_CONFIG.get(ENVIRONMENT, ENV_CONFIG["local"])

# =============================================================================
# RESPONSE PARSING AND COORDINATION FUNCTIONS
# =============================================================================

def parse_extraction_response(**context) -> Dict[str, Any]:
    """
    Parse Lambda extractor response and prepare coordination data.
    Works with both LocalStack and real Lambda responses.
    """
    task_instance = context['task_instance']

    # Get the Lambda response from the invoke task
    lambda_response = task_instance.xcom_pull(task_ids='invoke_api_extractor')
    logger.info(f"Raw Lambda response received: {type(lambda_response)}")

    # Parse Lambda response - handle different response formats
    if lambda_response is None:
        logger.error("Lambda response is None - this means the invoke_api_extractor task didn't run or failed")
        raise AirflowException("No Lambda response found - previous task may have failed")
    elif isinstance(lambda_response, dict):
        # Direct response dict
        response_body = lambda_response
        logger.info(f"Using direct response dict")
    elif isinstance(lambda_response, str):
        # JSON string response (common with LocalStack)
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

    # Validate successful extraction
    if not response_body.get('success', False):
        error_msg = response_body.get('message', 'Unknown extraction error')
        logger.error(f"Lambda extraction failed: {error_msg}")
        raise AirflowException(f"API extraction failed: {error_msg}")

    # Extract coordination data
    extraction_data = response_body.get('data', {})

    # Enhanced logging for monitoring and debugging
    logger.info(f"✅ Extraction completed successfully:")
    logger.info(f"   - Environment: {ENVIRONMENT}")
    logger.info(f"   - Function: {config['api_extractor_function']}")
    logger.info(f"   - Files created: {extraction_data.get('file_count', 'N/A')}")
    logger.info(f"   - Total records: {extraction_data.get('total_records', 'N/A')}")
    logger.info(f"   - Source prefix: {extraction_data.get('source_prefix', 'N/A')}")
    logger.info(f"   - Bucket: {extraction_data.get('bucket', config.get('bucket_name', 'N/A'))}")

    # Prepare payload for transformer
    transformer_payload = extraction_data.get('transformer_payload', {})

    # Ensure transformer payload has required fields
    if not transformer_payload:
        logger.warning("No transformer_payload found in extraction response, creating one")
        transformer_payload = {
            'bucket_name': extraction_data.get('bucket', config['bucket_name']),
            'semantic_identifier': extraction_data.get('semantic_identifier', 'social_services'),
            'downloaded_date': extraction_data.get('downloaded_date', datetime.utcnow().strftime('%Y%m%d')),
            'file_count': extraction_data.get('file_count', 0),
            'total_records': extraction_data.get('total_records', 0),
            'source_prefix': extraction_data.get('source_prefix', ''),
            'extraction_timestamp': extraction_data.get('extraction_completed_at', datetime.utcnow().isoformat())
        }

    # Store coordination data for next tasks
    task_instance.xcom_push(key='transformer_payload', value=transformer_payload)
    task_instance.xcom_push(key='extraction_metadata', value=extraction_data)

    logger.info(f"Prepared transformer payload: {json.dumps(transformer_payload, indent=2, default=str)}")

    return extraction_data

def validate_extraction_results(**context) -> str:
    """
    Validate extraction results and apply business rules.
    Pure coordination logic - no heavy processing.
    """
    task_instance = context['task_instance']
    
    # Debug: Check what XCom data is available
    logger.info("🔍 Checking available XCom data...")
    try:
        # Try to get all XCom data from parse_extraction_response
        all_xcom_data = task_instance.xcom_pull(task_ids='parse_extraction_response')
        logger.info(f"All XCom data from parse_extraction_response: {all_xcom_data}")
        
        # Get the specific key
        extraction_data = task_instance.xcom_pull(task_ids='parse_extraction_response', key='extraction_metadata')
        logger.info(f"Extraction metadata: {extraction_data}")
        
    except Exception as e:
        logger.error(f"Error retrieving XCom data: {e}")
        raise AirflowException(f"Failed to retrieve XCom data: {e}")

    if not extraction_data:
        logger.error("extraction_data is None or empty")
        # Try alternative approach - get the return value of parse_extraction_response
        extraction_data = task_instance.xcom_pull(task_ids='parse_extraction_response')
        logger.info(f"Trying return value instead: {extraction_data}")
        
        if not extraction_data:
            raise AirflowException("No extraction metadata found - previous task may have failed")

    # Business validation rules
    min_expected_records = 100  # Minimum expected for social services data
    file_count = extraction_data.get('file_count', 0)
    total_records = extraction_data.get('total_records', 0)
    bucket_name = extraction_data.get('bucket', 'unknown')

    logger.info(f"🔍 Validating extraction results:")
    logger.info(f"   - Environment: {ENVIRONMENT} ({'LocalStack' if config.get('use_localstack') else 'AWS'})")
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
        # Continue processing but flag for investigation

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
    logger.info(f"   - Input records: {transformation_data.get('input_records', 'N/A')}")
    logger.info(f"   - Output records: {transformation_data.get('output_records', 'N/A')}")
    logger.info(f"   - Staging files: {transformation_data.get('staging_files_created', 'N/A')}")
    logger.info(f"   - Staging prefix: {transformation_data.get('staging_prefix', 'N/A')}")

    # Store transformation metadata for potential downstream tasks
    task_instance.xcom_push(key='transformation_metadata', value=transformation_data)

    return transformation_data

def trigger_dbt_workflow(**context) -> str:
    """
    Trigger DBT workflow with staging data.
    Lightweight coordination function for DBT integration.
    """
    task_instance = context['task_instance']

    # Get metadata from previous tasks
    extraction_data = task_instance.xcom_pull(task_ids='parse_extraction_response', key='extraction_metadata')
    transformation_data = task_instance.xcom_pull(task_ids='parse_transformation_response', key='transformation_metadata')

    logger.info("🚀 Preparing DBT workflow trigger...")
    logger.info(f"   - Environment: {ENVIRONMENT}")

    if extraction_data:
        logger.info(f"   - Extracted records: {extraction_data.get('total_records', 'N/A')}")
        logger.info(f"   - Source prefix: {extraction_data.get('source_prefix', 'N/A')}")

    if transformation_data:
        logger.info(f"   - Transformed records: {transformation_data.get('output_records', 'N/A')}")
        logger.info(f"   - Staging prefix: {transformation_data.get('staging_prefix', 'N/A')}")

    # In LocalStack environment, log that DBT would be triggered
    if config.get("use_localstack", False):
        logger.info("📊 LocalStack environment: DBT workflow would be triggered here")
        logger.info("   - Data is available in LocalStack S3 for DBT processing")
        logger.info("   - Next: Configure DBT to connect to LocalStack S3")
    else:
        logger.info("📊 AWS environment: Triggering DBT workflow")
        logger.info("   - Staging data ready for marts transformation")

    # Store trigger information for potential DAG chaining
    task_instance.xcom_push(key='dbt_trigger_data', value={
        'environment': ENVIRONMENT,
        'trigger_time': datetime.utcnow().isoformat(),
        'source_records': extraction_data.get('total_records') if extraction_data else None,
        'staging_records': transformation_data.get('output_records') if transformation_data else None,
        'staging_location': transformation_data.get('staging_prefix') if transformation_data else None
    })

    return "dbt_workflow_triggered"

# =============================================================================
# DAG DEFINITION
# =============================================================================

dag = DAG(
    'catalunya_social_services_localstack_pipeline',
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
    description=f'Catalunya Social Services Pipeline - {ENVIRONMENT} environment (LocalStack integrated)',
    schedule=config['schedule'],
    catchup=False,
    max_active_runs=1,
    tags=['catalunya', 'social-services', 'localstack', f'env:{ENVIRONMENT}']
)

# =============================================================================
# TASK CREATION - LOCALSTACK AND AWS COMPATIBLE
# =============================================================================

logger.info(f"🏗️  Creating pipeline tasks for {ENVIRONMENT} environment")
logger.info(f"   - LocalStack mode: {config.get('use_localstack', False)}")
logger.info(f"   - AWS Connection ID: {config['aws_conn_id']}")
logger.info(f"   - Extractor function: {config['api_extractor_function']}")
logger.info(f"   - Transformer function: {config['transformer_function']}")

# Task 1: Invoke API Extractor Lambda (LocalStack or AWS)
invoke_api_extractor = LambdaInvokeFunctionOperator(
    task_id='invoke_api_extractor',
    function_name=config['api_extractor_function'],
    aws_conn_id=config['aws_conn_id'],
    invocation_type='RequestResponse',  # Synchronous invocation
    payload=json.dumps({
        'source': 'airflow.orchestrator',
        'environment': ENVIRONMENT,
        'trigger_time': '{{ ts }}',
        'dag_run_id': '{{ dag_run.run_id }}',
        'task_instance_key_str': '{{ task_instance_key_str }}',
        'use_localstack': config.get('use_localstack', False),
        'bucket_name': config['bucket_name']
    }),
    dag=dag
)

# Task 2: Parse and validate extraction response
parse_extraction_response = PythonOperator(
    task_id='parse_extraction_response',
    python_callable=parse_extraction_response,
    dag=dag
)

# Task 3: Validate extraction results
validate_extraction_results = PythonOperator(
    task_id='validate_extraction_results',
    python_callable=validate_extraction_results,
    dag=dag
)

# Task 4: Invoke Transformer Lambda (LocalStack or AWS)
invoke_transformer = LambdaInvokeFunctionOperator(
    task_id='invoke_transformer',
    function_name=config['transformer_function'],
    aws_conn_id=config['aws_conn_id'],
    invocation_type='RequestResponse',
    payload='{{ task_instance.xcom_pull(key="transformer_payload") | tojson }}',
    dag=dag
)

# Task 5: Parse transformation response
parse_transformation_response = PythonOperator(
    task_id='parse_transformation_response',
    python_callable=parse_transformation_response,
    dag=dag
)

# Task 6: Trigger DBT workflow
trigger_dbt_workflow_task = PythonOperator(
    task_id='trigger_dbt_workflow',
    python_callable=trigger_dbt_workflow,
    dag=dag
)

# =============================================================================
# TASK DEPENDENCIES
# =============================================================================

# Linear pipeline flow with proper error handling at each stage
(invoke_api_extractor >>
 parse_extraction_response >>
 validate_extraction_results >>
 invoke_transformer >>
 parse_transformation_response >>
 trigger_dbt_workflow_task)