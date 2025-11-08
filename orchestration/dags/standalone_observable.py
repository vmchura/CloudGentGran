from datetime import datetime, timedelta
from airflow import DAG
from airflow.models import Variable
from operators.observable_build_operator import ObservableBuildDeployOperator

ENVIRONMENT = Variable.get("environment")

ENV_CONFIG = {
    "local": {
        "aws_conn_id": "localstack_default",
        "data_bucket": "catalunya-data-dev",
        "schedule": timedelta(hours=6),
        "timeout_minutes": 30,
        "retry_attempts": 1,
        "retry_delay": timedelta(minutes=2)
    },
    "dev": {
        "aws_conn_id": "aws_cross_account_role",
        "data_bucket": "catalunya-data-dev",
        "schedule": "0 2 * * *",  # Daily at 2 AM
        "timeout_minutes": 30,
        "retry_attempts": 2,
        "retry_delay": timedelta(minutes=5)
    },
    "prod": {
        "aws_conn_id": "aws_lambda_role_conn",
        "data_bucket": "catalunya-data-prod",
        "schedule": "0 3 * * *",  # Daily at 3 AM
        "timeout_minutes": 45,
        "retry_attempts": 2,
        "retry_delay": timedelta(minutes=5)
    }
}

config = ENV_CONFIG[ENVIRONMENT]

dag = DAG(
    'catalunya_observable_deploy',
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
    description=f'Catalunya Observable Build and Deploy - {ENVIRONMENT}',
    schedule=config['schedule'],
    catchup=False,
    max_active_runs=1,
    tags=['catalunya', 'observable', 'frontend', f'env:{ENVIRONMENT}']
)

build_and_deploy_observable = ObservableBuildDeployOperator(
    task_id='build_and_deploy_observable',
    repository_url='https://github.com/vmchura/CloudGentGran',
    bucket_name=config['data_bucket'],
    environment=ENVIRONMENT,
    s3_prefix='dataservice/observable',
    aws_conn_id=config['aws_conn_id'],
    dag=dag
)

(build_and_deploy_observable)