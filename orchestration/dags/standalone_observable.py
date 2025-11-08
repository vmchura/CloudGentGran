import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from airflow import DAG
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
        "api_extractor_function": "catalunya-dev-social_services",
        "transformer_function": "catalunya-dev-social-services-transformer",
        "catalog_bucket": "catalunya-catalog-dev",
        "data_bucket": "catalunya-data-dev",
        "athena_database_name": "catalunya_data_dev",
        "schedule": timedelta(hours=2),  # More frequent for testing
        "timeout_minutes": 15,
        "retry_attempts": 1,
        "retry_delay": timedelta(minutes=2),
        "observable_build_function": "catalunya-dev-node-build-deploy",
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
        "retry_delay": timedelta(minutes=5),
        "observable_build_function": "catalunya-dev-node-build-deploy",
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
        "retry_delay": timedelta(minutes=5),
        "observable_build_function": "catalunya-prod-node-build-deploy",
    }
}

config = ENV_CONFIG[ENVIRONMENT]

# =============================================================================
# DAG DEFINITION
# =============================================================================

dag = DAG(
    'catalunya_social_services_deploy',
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
# PAYLOAD PREPARATION AND COORDINATION FUNCTIONS
# =============================================================================

invoke_observable_build = LambdaInvokeFunctionOperator(
    task_id='invoke_observable_build',
    function_name=config['observable_build_function'],
    aws_conn_id=config['aws_conn_id'],
    invocation_type='RequestResponse',  # Synchronous invocation
    dag=dag
)
(invoke_observable_build)