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
        "population_municipal_greater_65_function": "catalunya-dev-population_municipal_greater_65",
        "timeout_minutes": 10,
        "bucket_name": "catalunya-data-dev",
        "retry_attempts": 1,
        "retry_delay": timedelta(minutes=10)
    },
    "dev": {
        "aws_conn_id": "aws_cross_account_role",
        "population_municipal_greater_65_function": "catalunya-dev-population_municipal_greater_65",
        "timeout_minutes": 10,
        "bucket_name": "catalunya-data-dev",
        "retry_attempts": 1,
        "retry_delay": timedelta(minutes=10)
    },
    "prod": {
        "aws_conn_id": "aws_cross_account_role",
        "population_municipal_greater_65_function": "catalunya-prod-population_municipal_greater_65",
        "timeout_minutes": 10,
        "bucket_name": "catalunya-data-prod",
        "retry_attempts": 1,
        "retry_delay": timedelta(minutes=10)
    }
}

config = ENV_CONFIG.get(ENVIRONMENT)

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
    schedule=None,  # Manual trigger only - no scheduling
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=True,  # Disabled by default
    tags=['catalunya', 'long_term', 'initializer', 'manual', f'env:{ENVIRONMENT}']
)

population_municipal_greater_65_initializer = LambdaInvokeFunctionOperator(
    task_id='population_municipal_greater_65_initializer',
    function_name=config['population_municipal_greater_65_function'],
    aws_conn_id=config['aws_conn_id'],
    invocation_type='RequestResponse',  # Synchronous invocation
    dag=dag
)

population_municipal_greater_65_initializer