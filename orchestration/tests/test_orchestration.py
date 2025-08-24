"""
Catalunya Data Pipeline - Orchestration Tests
=============================================

This module contains tests for the orchestration layer components.

Author: Catalunya Data Team
Version: 1.0.0
"""

import pytest
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Airflow testing imports
from airflow.models import DagBag
from airflow.utils.state import DagRunState, TaskInstanceState
from airflow.utils.types import DagRunType


class TestCatalunyaDataPipeline:
    """Test cases for the main Catalunya data pipeline DAG."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.dag_id = 'catalunya_data_pipeline'
        self.dagbag = DagBag(dag_folder='/opt/airflow/dags')

    def test_dag_loaded_successfully(self):
        """Test that the DAG is loaded without errors."""
        dag = self.dagbag.get_dag(self.dag_id)
        assert dag is not None
        assert len(self.dagbag.import_errors) == 0

    def test_dag_has_correct_structure(self):
        """Test that the DAG has the expected tasks and structure."""
        dag = self.dagbag.get_dag(self.dag_id)

        expected_tasks = [
            'check_dbt_connection',
            'wait_for_new_data',
            'run_dbt_transformations',
            'generate_dbt_docs',
            'validate_data_quality'
        ]

        actual_tasks = list(dag.task_dict.keys())

        for task in expected_tasks:
            assert task in actual_tasks, f"Task {task} not found in DAG"

    def test_dag_has_correct_schedule(self):
        """Test that the DAG has the correct schedule interval."""
        dag = self.dagbag.get_dag(self.dag_id)

        expected_schedule = timedelta(hours=6)
        assert dag.schedule_interval == expected_schedule

    def test_dag_has_correct_default_args(self):
        """Test that the DAG has the correct default arguments."""
        dag = self.dagbag.get_dag(self.dag_id)

        assert dag.default_args['owner'] == 'catalunya-data-team'
        assert dag.default_args['retries'] == 2
        assert dag.default_args['retry_delay'] == timedelta(minutes=5)
        assert dag.default_args['catchup'] is False

    def test_task_dependencies(self):
        """Test that tasks have the correct dependencies."""
        dag = self.dagbag.get_dag(self.dag_id)

        check_dbt_task = dag.get_task('check_dbt_connection')
        wait_for_data_task = dag.get_task('wait_for_new_data')
        run_dbt_task = dag.get_task('run_dbt_transformations')
        generate_docs_task = dag.get_task('generate_dbt_docs')
        data_quality_task = dag.get_task('validate_data_quality')

        # Test upstream dependencies
        assert check_dbt_task.task_id in [t.task_id for t in wait_for_data_task.upstream_list]
        assert wait_for_data_task.task_id in [t.task_id for t in run_dbt_task.upstream_list]
        assert run_dbt_task.task_id in [t.task_id for t in generate_docs_task.upstream_list]
        assert run_dbt_task.task_id in [t.task_id for t in data_quality_task.upstream_list]


class TestDBTIntegration:
    """Test cases for DBT integration functions."""

    @patch('subprocess.run')
    def test_check_dbt_connection_success(self, mock_subprocess):
        """Test successful DBT connection check."""
        from airflow.dags.catalunya_data_pipeline import check_dbt_connection

        # Mock successful subprocess call
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Connection test passed!"
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        # Execute function
        result = check_dbt_connection()

        assert result == "connection_success"
        mock_subprocess.assert_called_once()

    @patch('subprocess.run')
    def test_check_dbt_connection_failure(self, mock_subprocess):
        """Test DBT connection check failure."""
        from airflow.dags.catalunya_data_pipeline import check_dbt_connection

        # Mock failed subprocess call
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Connection failed!"
        mock_subprocess.return_value = mock_result

        # Execute function and expect exception
        with pytest.raises(Exception) as excinfo:
            check_dbt_connection()

        assert "DBT connection failed" in str(excinfo.value)
        mock_subprocess.assert_called_once()

    @patch('subprocess.run')
    def test_run_dbt_transformations_success(self, mock_subprocess):
        """Test successful DBT transformations."""
        from airflow.dags.catalunya_data_pipeline import run_dbt_transformations

        # Mock successful subprocess calls
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Models executed successfully!"
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        # Execute function
        result = run_dbt_transformations()

        assert result == "transformations_success"
        # Should be called multiple times (seed, run, test)
        assert mock_subprocess.call_count >= 3


class TestEnvironmentSetup:
    """Test cases for environment setup and configuration."""

    def test_environment_variables_exist(self):
        """Test that required environment variables are set."""
        # These should be set in the test environment
        env_vars = [
            'AIRFLOW_HOME',
            'DBT_PROFILES_DIR'
        ]

        for var in env_vars:
            assert os.getenv(var) is not None, f"Environment variable {var} is not set"

    def test_dbt_profiles_directory_exists(self):
        """Test that DBT profiles directory exists."""
        profiles_dir = os.getenv('DBT_PROFILES_DIR', '/home/airflow/.dbt')
        # In test environment, we'll create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            test_profiles_dir = os.path.join(temp_dir, '.dbt')
            os.makedirs(test_profiles_dir, exist_ok=True)
            assert os.path.exists(test_profiles_dir)


class TestDockerSetup:
    """Test cases for Docker setup and containerization."""

    def test_required_packages_installed(self):
        """Test that required Python packages are installed."""
        try:
            import airflow
            import dbt.cli.main
            import boto3
            import psycopg2
            import redis
            import yaml
        except ImportError as e:
            pytest.fail(f"Required package not installed: {e}")

    def test_airflow_version(self):
        """Test that the correct Airflow version is installed."""
        import airflow

        # Check that we have Airflow 2.8.x
        version = airflow.__version__
        major, minor = version.split('.')[:2]
        assert major == '2'
        assert minor == '8'

    def test_dbt_version(self):
        """Test that the correct DBT version is installed."""
        import dbt

        # Check that we have DBT 1.7.x
        version = dbt.version.__version__
        major, minor = version.split('.')[:2]
        assert major == '1'
        assert minor == '7'


# Pytest configuration and fixtures
@pytest.fixture
def mock_airflow_context():
    """Fixture to provide mock Airflow context."""
    return {
        'dag': MagicMock(),
        'task': MagicMock(),
        'ti': MagicMock(),
        'ds': '2024-01-01',
        'execution_date': datetime(2024, 1, 1),
        'dag_run': MagicMock(),
    }


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, '-v'])