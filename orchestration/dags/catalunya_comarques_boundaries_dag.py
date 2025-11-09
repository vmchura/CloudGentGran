import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Variable
from airflow.exceptions import AirflowException
from airflow.providers.amazon.aws.operators.lambda_function import LambdaInvokeFunctionOperator
from operators.s3_copy_with_role_operator import S3CopyWithRoleOperator

logger = logging.getLogger(__name__)

ENVIRONMENT = Variable.get("environment")

ENV_CONFIG = {
    "local": {
        "aws_conn_id": "localstack_default",
        "extractor_function": "catalunya-dev-comarques_boundaries",
        "timeout_minutes": 10,
        "bucket_name": "catalunya-data-dev",
        "retry_attempts": 1,
        "retry_delay": timedelta(minutes=10)
    },
    "dev": {
        "aws_conn_id": "aws_cross_account_role",
        "extractor_function": "catalunya-dev-comarques_boundaries",
        "timeout_minutes": 10,
        "bucket_name": "catalunya-data-dev",
        "retry_attempts": 1,
        "retry_delay": timedelta(minutes=10)
    },
    "prod": {
        "aws_conn_id": "aws_cross_account_role",
        "extractor_function": "catalunya-prod-comarques_boundaries",
        "timeout_minutes": 10,
        "bucket_name": "catalunya-data-prod",
        "retry_attempts": 1,
        "retry_delay": timedelta(minutes=10)
    }
}

config = ENV_CONFIG.get(ENVIRONMENT)

def parse_extractor_response(**context):
    task_instance = context['task_instance']
    extractor_response = task_instance.xcom_pull(task_ids='invoke_extractor')
    extractor_response = json.loads(extractor_response) if isinstance(extractor_response, str) else extractor_response

    if not extractor_response or not extractor_response.get('success'):
        raise AirflowException("Extractor failed or returned invalid response")

    list_s3_keys = extractor_response['data']['list_s3_keys']
    logger.info(f"Extracted file at: {list_s3_keys}")

    return {
        'source_multiple_keys': list_s3_keys,
        'dest_staging_multiple_keys': [single_key.replace('landing/', 'staging/') for single_key in list_s3_keys ],
        'dest_mart_multiple_keys': [single_key.replace('landing/', 'marts/') for single_key in list_s3_keys ]
    }

dag = DAG(
    'catalunya_comarques_boundaries_update',
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
    description=f'Catalunya Comarques Boundaries Update - {ENVIRONMENT}',
    schedule=None,
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=True,
    tags=['catalunya', 'comarques', 'boundaries', 'manual', f'env:{ENVIRONMENT}']
)

invoke_extractor = LambdaInvokeFunctionOperator(
    task_id='invoke_extractor',
    function_name=config['extractor_function'],
    aws_conn_id=config['aws_conn_id'],
    invocation_type='RequestResponse',
    dag=dag
)

parse_response = PythonOperator(
    task_id='parse_response',
    python_callable=parse_extractor_response,
    dag=dag
)

copy_to_staging = S3CopyWithRoleOperator(
    task_id='copy_to_staging',
    aws_conn_id=config['aws_conn_id'],
    role_type='transformer',
    source_bucket_name=config['bucket_name'],
    source_bucket_key="{{ task_instance.xcom_pull(task_ids='parse_response')['source_multiple_keys'] }}",
    dest_bucket_name=config['bucket_name'],
    dest_bucket_key="{{ task_instance.xcom_pull(task_ids='parse_response')['dest_staging_multiple_keys'] }}",
    dag=dag
)

copy_to_mart = S3CopyWithRoleOperator(
    task_id='copy_to_mart',
    aws_conn_id=config['aws_conn_id'],
    role_type='mart',
    source_bucket_name=config['bucket_name'],
    source_bucket_key="{{ task_instance.xcom_pull(task_ids='parse_response')['dest_staging_multiple_keys'] }}",
    dest_bucket_name=config['bucket_name'],
    dest_bucket_key="{{ task_instance.xcom_pull(task_ids='parse_response')['dest_mart_multiple_keys'] }}",
    dag=dag
)

invoke_extractor >> parse_response >> copy_to_staging >> copy_to_mart