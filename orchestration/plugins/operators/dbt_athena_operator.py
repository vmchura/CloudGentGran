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

        # Get AWS credentials from connection (cross-account role)
        hook = AwsBaseHook(aws_conn_id=self.aws_conn_id)

        # Create STS client correctly
        sts_client = hook.get_session().client('sts')

        # Assume the mart execution role
        ENVIRONMENT = os.getenv('ENVIRONMENT')
        account_id = sts_client.get_caller_identity()['Account']
        mart_role_arn = f"arn:aws:iam::{account_id}:role/catalunya-mart-role-{ENVIRONMENT}"

        logger.info(f"Assuming mart role: {mart_role_arn}")

        assumed_role = sts_client.assume_role(
            RoleArn=mart_role_arn,
            RoleSessionName='dbt_execution'
        )

        # Use assumed role credentials
        credentials = assumed_role['Credentials']

        # Build DBT command
        dbt_cmd = self._build_dbt_command()
        logger.info(f"Executing DBT command: {' '.join(dbt_cmd)}")

        # Set environment with AWS credentials
        env = self._build_environment_from_assumed_role(credentials)

        # Rest of the method stays the same...

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

    def _build_environment_from_assumed_role(self, credentials) -> Dict[str, str]:
        env = os.environ.copy()

        env['AWS_ACCESS_KEY_ID'] = credentials['AccessKeyId']
        env['AWS_SECRET_ACCESS_KEY'] = credentials['SecretAccessKey']
        env['AWS_SESSION_TOKEN'] = credentials['SessionToken']
        env['AWS_DEFAULT_REGION'] = 'eu-west-1'

        env['DBT_TARGET'] = self.dbt_target
        env['DBT_PROJECT_DIR'] = self.dbt_project_dir
        env['DBT_PROFILES_DIR'] = self.dbt_profiles_dir

        return env

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