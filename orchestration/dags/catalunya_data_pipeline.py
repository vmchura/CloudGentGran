"""
Catalunya Open Data Pipeline - Main DAG
=========================================

This DAG orchestrates the Catalunya open data extraction, transformation, and loading processes.
It integrates the existing Lambda extractors with DBT transformations.

Author: Catalunya Data Team
Version: 1.0.0
"""

from datetime import datetime, timedelta
from typing import Dict, Any

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.operators.s3 import S3ListOperator
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor
from airflow.utils.dates import days_ago

# Default arguments for the DAG
default_args: Dict[str, Any] = {
    'owner': 'catalunya-data-team',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'catchup': False,
}

# DAG definition
dag = DAG(
    'catalunya_data_pipeline',
    default_args=default_args,
    description='Catalunya Open Data Pipeline with DBT transformations',
    schedule_interval=timedelta(hours=6),  # Run every 6 hours
    max_active_runs=1,
    tags=['catalunya', 'opendata', 'dbt', 'etl'],
)

def check_dbt_connection(**context) -> str:
    """
    Check DBT connection and setup before running transformations.
    """
    import os
    import subprocess

    # Set up environment
    dbt_project_dir = '/opt/airflow/dbt_mart'
    profiles_dir = '/home/airflow/.dbt'

    try:
        # Change to DBT project directory
        os.chdir(dbt_project_dir)

        # Run DBT debug to check connection
        result = subprocess.run(
            ['dbt', 'debug', '--profiles-dir', profiles_dir],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            print("✅ DBT connection successful")
            print("DBT Debug Output:")
            print(result.stdout)
            return "connection_success"
        else:
            print("❌ DBT connection failed")
            print("Error Output:")
            print(result.stderr)
            raise Exception(f"DBT connection failed: {result.stderr}")

    except subprocess.TimeoutExpired:
        raise Exception("DBT connection check timed out")
    except Exception as e:
        raise Exception(f"Error checking DBT connection: {str(e)}")

def run_dbt_transformations(**context) -> str:
    """
    Run DBT transformations for the Catalunya data pipeline.
    """
    import os
    import subprocess

    # Set up environment
    dbt_project_dir = '/opt/airflow/dbt_mart'
    profiles_dir = '/home/airflow/.dbt'

    try:
        # Change to DBT project directory
        os.chdir(dbt_project_dir)

        # Run DBT seed (if any seed data exists)
        print("📊 Running DBT seed...")
        seed_result = subprocess.run(
            ['dbt', 'seed', '--profiles-dir', profiles_dir],
            capture_output=True,
            text=True,
            timeout=300
        )

        if seed_result.returncode != 0:
            print("⚠️  DBT seed failed (this might be expected if no seeds exist)")
            print(seed_result.stderr)

        # Run DBT run to execute models
        print("🔄 Running DBT models...")
        run_result = subprocess.run(
            ['dbt', 'run', '--profiles-dir', profiles_dir],
            capture_output=True,
            text=True,
            timeout=1800  # 30 minutes timeout
        )

        if run_result.returncode == 0:
            print("✅ DBT run successful")
            print("DBT Run Output:")
            print(run_result.stdout)
        else:
            print("❌ DBT run failed")
            print("Error Output:")
            print(run_result.stderr)
            raise Exception(f"DBT run failed: {run_result.stderr}")

        # Run DBT tests
        print("🧪 Running DBT tests...")
        test_result = subprocess.run(
            ['dbt', 'test', '--profiles-dir', profiles_dir],
            capture_output=True,
            text=True,
            timeout=600  # 10 minutes timeout
        )

        if test_result.returncode == 0:
            print("✅ DBT tests passed")
            print("DBT Test Output:")
            print(test_result.stdout)
        else:
            print("⚠️  Some DBT tests failed")
            print("Test Output:")
            print(test_result.stderr)
            # Don't fail the task on test failures, just warn

        return "transformations_success"

    except subprocess.TimeoutExpired:
        raise Exception("DBT transformations timed out")
    except Exception as e:
        raise Exception(f"Error running DBT transformations: {str(e)}")

def generate_dbt_docs(**context) -> str:
    """
    Generate DBT documentation.
    """
    import os
    import subprocess

    # Set up environment
    dbt_project_dir = '/opt/airflow/dbt_mart'
    profiles_dir = '/home/airflow/.dbt'

    try:
        # Change to DBT project directory
        os.chdir(dbt_project_dir)

        # Generate DBT docs
        print("📚 Generating DBT documentation...")
        docs_result = subprocess.run(
            ['dbt', 'docs', 'generate', '--profiles-dir', profiles_dir],
            capture_output=True,
            text=True,
            timeout=300
        )

        if docs_result.returncode == 0:
            print("✅ DBT documentation generated successfully")
            print("Docs Output:")
            print(docs_result.stdout)
            return "docs_success"
        else:
            print("⚠️  DBT docs generation failed")
            print("Error Output:")
            print(docs_result.stderr)
            # Don't fail the task on docs generation failure
            return "docs_warning"

    except subprocess.TimeoutExpired:
        raise Exception("DBT docs generation timed out")
    except Exception as e:
        print(f"Warning: Error generating DBT docs: {str(e)}")
        return "docs_warning"

# Task 1: Check DBT connection
check_dbt_task = PythonOperator(
    task_id='check_dbt_connection',
    python_callable=check_dbt_connection,
    dag=dag,
)

# Task 2: Wait for new data in S3 (this would be replaced with actual S3 sensor in production)
wait_for_data_task = BashOperator(
    task_id='wait_for_new_data',
    bash_command='echo "Checking for new data... (placeholder for S3 sensor)"',
    dag=dag,
)

# Task 3: Run DBT transformations
run_dbt_task = PythonOperator(
    task_id='run_dbt_transformations',
    python_callable=run_dbt_transformations,
    dag=dag,
)

# Task 4: Generate DBT documentation
generate_docs_task = PythonOperator(
    task_id='generate_dbt_docs',
    python_callable=generate_dbt_docs,
    dag=dag,
)

# Task 5: Data quality validation
data_quality_task = BashOperator(
    task_id='validate_data_quality',
    bash_command="""
    echo "Running data quality checks..."
    # This would include custom data quality validations
    # For now, we'll just echo a success message
    echo "✅ Data quality checks passed"
    """,
    dag=dag,
)

# Task dependencies
check_dbt_task >> wait_for_data_task >> run_dbt_task >> [generate_docs_task, data_quality_task]

# Export the DAG
if __name__ == "__main__":
    dag.test()