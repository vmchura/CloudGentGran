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

ENVIRONMENT = Variable.get("environment")

ENV_CONFIG = {
    "local": {
        "aws_conn_id": "localstack_default",
        "population_municipal_greater_65_function": "catalunya-dev-population_municipal_greater_65",
        "population_municipal_greater_65_transformer_function": "catalunya-dev-population_municipal_greater_65-transformer",
        "population_municipal_greater_65_mart_function": "catalunya-dev-population_municipal_greater_65-mart",
        "timeout_minutes": 10,
        "bucket_name": "catalunya-data-dev",
        "retry_attempts": 1,
        "retry_delay": timedelta(minutes=10)
    },
    "dev": {
        "aws_conn_id": "aws_cross_account_role",
        "population_municipal_greater_65_function": "catalunya-dev-population_municipal_greater_65",
        "population_municipal_greater_65_transformer_function": "catalunya-dev-population_municipal_greater_65-transformer",
        "population_municipal_greater_65_mart_function": "catalunya-dev-population_municipal_greater_65-mart",
        "timeout_minutes": 10,
        "bucket_name": "catalunya-data-dev",
        "retry_attempts": 1,
        "retry_delay": timedelta(minutes=10)
    },
    "prod": {
        "aws_conn_id": "aws_cross_account_role",
        "population_municipal_greater_65_function": "catalunya-prod-population_municipal_greater_65",
        "population_municipal_greater_65_transformer_function": "catalunya-prod-population_municipal_greater_65-transformer",
        "population_municipal_greater_65_mart_function": "catalunya-prod-population_municipal_greater_65-mart",
        "timeout_minutes": 10,
        "bucket_name": "catalunya-data-prod",
        "retry_attempts": 1,
        "retry_delay": timedelta(minutes=10)
    }
}

config = ENV_CONFIG.get(ENVIRONMENT)

def extract_source_prefix(**context):
    task_instance = context['task_instance']
    extractor_response = task_instance.xcom_pull(task_ids='population_municipal_greater_65_initializer')
    extractor_response = json.loads(extractor_response) if isinstance(extractor_response, str) else extractor_response
    if not extractor_response or not extractor_response.get('success'):
        raise AirflowException("Extractor failed or returned invalid response")
    return {
        'source_prefix': f"landing/{extractor_response['data']['semantic_identifier']}/"
    }

def extract_transformer_target(**context):
    task_instance = context['task_instance']
    transformer_response = task_instance.xcom_pull(task_ids='population_municipal_greater_65_transformer')
    transformer_response = json.loads(transformer_response) if isinstance(transformer_response, str) else transformer_response
    if not transformer_response or transformer_response.get('status') != 'succeeded':
        raise AirflowException("Transformer failed or returned invalid response")
    return {
        'source_prefix': transformer_response.get('target_prefix')
    }

def validate_mart_completion(**context):
    task_instance = context['task_instance']
    mart_response = task_instance.xcom_pull(task_ids='population_municipal_greater_65_mart')
    mart_response = json.loads(mart_response) if isinstance(mart_response, str) else mart_response
    if not mart_response or mart_response.get('status') != 'succeeded':
        raise AirflowException("Mart failed or returned invalid response")
    logger.info(f"Mart completed successfully. Target: {mart_response.get('target_prefix')}")

dag = DAG(
    'catalunya_long_term_update',
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
    description=f'Catalunya Long Term Update - {ENVIRONMENT} environment',
    schedule=None,
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=True,
    tags=['catalunya', 'long_term', 'initializer', 'manual', f'env:{ENVIRONMENT}']
)

population_municipal_greater_65_initializer = LambdaInvokeFunctionOperator(
    task_id='population_municipal_greater_65_initializer',
    function_name=config['population_municipal_greater_65_function'],
    aws_conn_id=config['aws_conn_id'],
    invocation_type='RequestResponse',
    dag=dag
)

prepare_transformer_payload = PythonOperator(
    task_id='prepare_transformer_payload',
    python_callable=extract_source_prefix,
    dag=dag
)

population_municipal_greater_65_transformer = LambdaInvokeFunctionOperator(
    task_id='population_municipal_greater_65_transformer',
    function_name=config['population_municipal_greater_65_transformer_function'],
    aws_conn_id=config['aws_conn_id'],
    invocation_type='RequestResponse',
    payload="{{ task_instance.xcom_pull(task_ids='prepare_transformer_payload') | tojson }}",
    dag=dag
)

prepare_mart_payload = PythonOperator(
    task_id='prepare_mart_payload',
    python_callable=extract_transformer_target,
    dag=dag
)

population_municipal_greater_65_mart = LambdaInvokeFunctionOperator(
    task_id='population_municipal_greater_65_mart',
    function_name=config['population_municipal_greater_65_mart_function'],
    aws_conn_id=config['aws_conn_id'],
    invocation_type='RequestResponse',
    payload="{{ task_instance.xcom_pull(task_ids='prepare_mart_payload') | tojson }}",
    dag=dag
)

validate_mart = PythonOperator(
    task_id='validate_mart',
    python_callable=validate_mart_completion,
    dag=dag
)

population_municipal_greater_65_initializer >> prepare_transformer_payload >> population_municipal_greater_65_transformer >> prepare_mart_payload >> population_municipal_greater_65_mart >> validate_mart