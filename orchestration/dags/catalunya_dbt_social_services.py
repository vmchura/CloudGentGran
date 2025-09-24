from datetime import datetime, timedelta
from airflow import DAG
from airflow.models import Variable
from operators.dbt_athena_operator import DbtAthenaOperator

ENVIRONMENT = Variable.get("environment")

dag = DAG(
    'catalunya_dbt_social_services',
    default_args={
        'owner': 'catalunya-data-team',
        'depends_on_past': False,
        'start_date': datetime(2024, 1, 1),
        'email_on_failure': True,
        'retries': 2,
        'retry_delay': timedelta(minutes=5),
        'execution_timeout': timedelta(minutes=30)
    },
    description=f'DBT Social Services Mart - {ENVIRONMENT}',
    schedule=None,
    catchup=False,
    max_active_runs=1,
    params={"downloaded_date": "20250920"},
    tags=['catalunya', 'dbt', 'social-services', 'mart', f'env:{ENVIRONMENT}']
)

run_dbt_model = DbtAthenaOperator(
    task_id='run_social_services_mart',
    aws_conn_id='aws_cross_account_role',
    dbt_command='run',
    dbt_target=ENVIRONMENT,
    dbt_vars={"downloaded_date": "{{ params.downloaded_date }}"},
    select_models='models.marts.social_services_mart',
    dag=dag
)

run_dbt_model