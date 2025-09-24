import os
import subprocess
import logging
from typing import List, Optional, Dict, Any

from airflow.models import BaseOperator
from airflow.providers.amazon.aws.hooks.base_aws import AwsBaseHook
from airflow.utils.context import Context
from airflow.exceptions import AirflowException

logger = logging.getLogger(__name__)

class DbtAthenaOperator(BaseOperator):
    template_fields = ['dbt_vars', 'select_models']

    def __init__(
            self,
            aws_conn_id: str,
            dbt_command: str = 'run',
            dbt_target: str = 'dev',
            dbt_vars: Optional[Dict[str, str]] = None,
            select_models: Optional[str] = None,
            dbt_project_dir: str = '/opt/airflow/dbt/mart',
            dbt_profiles_dir: str = '/opt/airflow/dbt',
            **kwargs
    ):
        super().__init__(**kwargs)
        self.aws_conn_id = aws_conn_id
        self.dbt_command = dbt_command
        self.dbt_target = dbt_target
        self.dbt_vars = dbt_vars or {}
        self.select_models = select_models
        self.dbt_project_dir = dbt_project_dir
        self.dbt_profiles_dir = dbt_profiles_dir

    def execute(self, context: Context) -> str:
        logger.info(f"Starting DBT {self.dbt_command} with target: {self.dbt_target}")

        # Get AWS credentials from connection
        hook = AwsBaseHook(aws_conn_id=self.aws_conn_id, client_type='sts')
        credentials = hook.get_credentials()

        # Build DBT command
        dbt_cmd = self._build_dbt_command()
        logger.info(f"Executing DBT command: {' '.join(dbt_cmd)}")

        # Set environment with AWS credentials
        env = self._build_environment(credentials)

        # Execute DBT command
        try:
            result = subprocess.run(
                dbt_cmd,
                env=env,
                capture_output=True,
                text=True,
                cwd=self.dbt_project_dir,
                timeout=1800  # 30 minutes timeout
            )

            # Log output
            if result.stdout:
                logger.info(f"DBT stdout:\n{result.stdout}")
            if result.stderr:
                logger.warning(f"DBT stderr:\n{result.stderr}")

            # Check execution result
            if result.returncode != 0:
                raise AirflowException(
                    f"DBT command failed with return code {result.returncode}:\n"
                    f"STDOUT: {result.stdout}\n"
                    f"STDERR: {result.stderr}"
                )

            logger.info("DBT command completed successfully")
            return result.stdout

        except subprocess.TimeoutExpired:
            raise AirflowException("DBT command timed out after 30 minutes")
        except Exception as e:
            raise AirflowException(f"Failed to execute DBT command: {str(e)}")

    def _build_dbt_command(self) -> List[str]:
        cmd = ['dbt', self.dbt_command]

        # Add target
        cmd.extend(['--target', self.dbt_target])

        # Add profiles directory
        cmd.extend(['--profiles-dir', self.dbt_profiles_dir])

        # Add variables if provided
        if self.dbt_vars:
            import json
            vars_json = json.dumps(self.dbt_vars)
            cmd.extend(['--vars', vars_json])

        # Add model selection if provided
        if self.select_models:
            cmd.extend(['--select', self.select_models])

        return cmd

    def _build_environment(self, credentials) -> Dict[str, str]:
        env = os.environ.copy()

        # AWS credentials
        env['AWS_ACCESS_KEY_ID'] = credentials.access_key
        env['AWS_SECRET_ACCESS_KEY'] = credentials.secret_key
        if credentials.token:
            env['AWS_SESSION_TOKEN'] = credentials.token
        env['AWS_DEFAULT_REGION'] = 'eu-west-1'

        # DBT specific
        env['DBT_TARGET'] = self.dbt_target
        env['DBT_PROJECT_DIR'] = self.dbt_project_dir
        env['DBT_PROFILES_DIR'] = self.dbt_profiles_dir

        return env