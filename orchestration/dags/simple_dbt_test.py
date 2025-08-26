"""
Simple Catalunya DBT Pipeline - Testing DAG
===========================================

A simplified DAG for testing local DBT integration with existing models.
This DAG focuses on running the DBT models you already have in the dbt/mart directory.

Author: Catalunya Data Team
Version: 1.0.0
"""

from datetime import datetime, timedelta
from typing import Dict, Any
import os

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

# Default arguments for the DAG
default_args: Dict[str, Any] = {
    'owner': 'catalunya-data-team',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
    'catchup': False,
}

# DAG definition
dag = DAG(
    'simple_dbt_test',
    default_args=default_args,
    description='Simple DBT test with Catalunya social services models',
    schedule_interval=None,  # Manual trigger only for testing
    max_active_runs=1,
    tags=['catalunya', 'dbt', 'test', 'local'],
)

def check_environment(**context) -> str:
    """Check the environment and DBT setup."""
    import subprocess

    print("🔍 Environment Check:")
    print(f"DBT_PROJECT_DIR: {os.getenv('DBT_PROJECT_DIR', 'NOT SET')}")
    print(f"DBT_PROFILES_DIR: {os.getenv('DBT_PROFILES_DIR', 'NOT SET')}")
    print(f"Current working directory: {os.getcwd()}")

    # Check if DBT project exists
    dbt_project_dir = os.getenv('DBT_PROJECT_DIR', '/opt/airflow/dbt/mart')
    profiles_dir = os.getenv('DBT_PROFILES_DIR', '/home/airflow/.dbt')

    if os.path.exists(dbt_project_dir):
        print(f"✅ DBT project directory found: {dbt_project_dir}")
        print("\n📁 DBT project contents:")
        for item in os.listdir(dbt_project_dir):
            print(f"  - {item}")
        if os.path.exists(f"{dbt_project_dir}/dbt_project.yml"):
            print("✅ dbt_project.yml found")
        else:
            print("❌ dbt_project.yml NOT found")
    else:
        print(f"❌ DBT project directory NOT found: {dbt_project_dir}")

    if os.path.exists(profiles_dir):
        print(f"✅ DBT profiles directory found: {profiles_dir}")
        if os.path.exists(f"{profiles_dir}/profiles.yml"):
            print("✅ profiles.yml found")
        else:
            print("❌ profiles.yml NOT found")
    else:
        print(f"❌ DBT profiles directory NOT found: {profiles_dir}")

    # Check DBT version
    try:
        result = subprocess.run(['dbt', '--version'], capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(f"✅ DBT installed: {result.stdout.strip()}")
        else:
            print(f"❌ DBT version check failed: {result.stderr}")
    except Exception as e:
        print(f"❌ Error checking DBT version: {str(e)}")

    return "environment_checked"

def run_dbt_debug(**context) -> str:
    """Run DBT debug to check connection and setup."""
    import subprocess

    dbt_project_dir = os.getenv('DBT_PROJECT_DIR', '/opt/airflow/dbt/mart')
    profiles_dir = os.getenv('DBT_PROFILES_DIR', '/home/airflow/.dbt')

    try:
        os.chdir(dbt_project_dir)
        print(f"Changed directory to: {os.getcwd()}")

        print("🔍 Running DBT debug...")
        result = subprocess.run(
            ['dbt', 'debug', '--profiles-dir', profiles_dir],
            capture_output=True, text=True, timeout=60
        )

        print("DBT Debug Output:")
        print("=" * 50)
        print(result.stdout)

        if result.stderr:
            print("DBT Debug Errors:")
            print("=" * 50)
            print(result.stderr)

        if result.returncode == 0:
            print("✅ DBT debug successful - ready to run models!")
            return "debug_success"
        else:
            print("❌ DBT debug failed")
            raise Exception(f"DBT debug failed with return code {result.returncode}")

    except subprocess.TimeoutExpired:
        raise Exception("DBT debug timed out")
    except Exception as e:
        raise Exception(f"Error running DBT debug: {str(e)}")

def create_sample_data(**context) -> str:
    """Create sample data for testing the DBT models locally."""
    import pandas as pd

    dbt_project_dir = os.getenv('DBT_PROJECT_DIR', '/opt/airflow/dbt/mart')
    staging_path = f"{dbt_project_dir}/local_data/staging/social_services"

    # Create directory if it doesn't exist
    os.makedirs(staging_path, exist_ok=True)

    # Create sample social services data
    sample_data = pd.DataFrame({
        'id': [1, 2, 3, 4, 5],
        'service_name': [
            'Centro de Salud Barcelona Norte',
            'Biblioteca Pública Sant Martí',
            'Centro de Servicios Sociales Gràcia',
            'Oficina de Atención Ciudadana Eixample',
            'Centro Deportivo Municipal Sants'
        ],
        'service_type': ['health', 'education', 'social', 'administrative', 'sports'],
        'district': ['Sant Andreu', 'Sant Martí', 'Gràcia', 'Eixample', 'Sants-Montjuïc'],
        'address': [
            'Carrer Gran de Sant Andreu, 123',
            'Carrer de Mallorca, 456',
            'Carrer de Gràcia, 789',
            'Carrer de Balmes, 321',
            'Carrer de Sants, 654'
        ],
        'created_at': pd.Timestamp.now(),
        'updated_at': pd.Timestamp.now()
    })

    # Save as parquet file
    output_path = f"{staging_path}/social_services_sample.parquet"
    sample_data.to_parquet(output_path, index=False)

    print(f"✅ Sample data created at: {output_path}")
    print(f"📊 Created {len(sample_data)} sample records")

    return "sample_data_created"

def run_dbt_models(**context) -> str:
    """Run the DBT models that exist in the project."""
    import subprocess

    dbt_project_dir = os.getenv('DBT_PROJECT_DIR', '/opt/airflow/dbt/mart')
    profiles_dir = os.getenv('DBT_PROFILES_DIR', '/home/airflow/.dbt')

    try:
        os.chdir(dbt_project_dir)

        print("🔄 Running DBT models...")
        result = subprocess.run(
            ['dbt', 'run', '--profiles-dir', profiles_dir],
            capture_output=True, text=True, timeout=300
        )

        print("DBT Run Output:")
        print("=" * 50)
        print(result.stdout)

        if result.stderr:
            print("DBT Run Errors:")
            print("=" * 50)
            print(result.stderr)

        if result.returncode == 0:
            print("✅ DBT models ran successfully!")
            return "models_success"
        else:
            print("❌ DBT models failed")
            raise Exception(f"DBT run failed: {result.stderr}")

    except subprocess.TimeoutExpired:
        raise Exception("DBT run timed out")
    except Exception as e:
        raise Exception(f"Error running DBT models: {str(e)}")

# Define tasks
check_env_task = PythonOperator(
    task_id='check_environment',
    python_callable=check_environment,
    dag=dag,
)

dbt_debug_task = PythonOperator(
    task_id='dbt_debug',
    python_callable=run_dbt_debug,
    dag=dag,
)

create_data_task = PythonOperator(
    task_id='create_sample_data',
    python_callable=create_sample_data,
    dag=dag,
)

run_models_task = PythonOperator(
    task_id='run_dbt_models',
    python_callable=run_dbt_models,
    dag=dag,
)

validate_task = BashOperator(
    task_id='validate_results',
    bash_command="""
    echo "🔍 Validation Results:"
    echo "====================="
    
    # Check if DuckDB file was created
    if [ -f "/opt/airflow/dbt/mart/local_data/catalunya_dev.duckdb" ]; then
        echo "✅ DuckDB file created successfully"
        ls -la /opt/airflow/dbt/mart/local_data/catalunya_dev.duckdb
    else
        echo "❌ DuckDB file NOT found"
    fi
    
    # Check local_data directory contents
    echo "📁 Local data directory contents:"
    ls -la /opt/airflow/dbt/mart/local_data/ || echo "Directory not found"
    
    echo "🎉 Validation completed!"
    """,
    dag=dag,
)

# Set task dependencies
check_env_task >> dbt_debug_task >> create_data_task >> run_models_task >> validate_task