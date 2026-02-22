import os
import subprocess
import logging
import boto3
from typing import List, Optional, Dict, Any

from airflow.sdk import BaseOperator
from airflow.providers.amazon.aws.hooks.base_aws import AwsBaseHook
from airflow.sdk import Context
from airflow.exceptions import AirflowException

logger = logging.getLogger(__name__)


class DbtAthenaOperator(BaseOperator):
    template_fields = ["dbt_vars", "select_models", "data_bucket"]

    def __init__(
        self,
        aws_conn_id: str,
        dbt_command: str = "run",
        dbt_target: str = "dev",
        dbt_vars: Optional[Dict[str, str]] = None,
        select_models: Optional[str] = None,
        data_bucket: Optional[str] = None,
        dbt_project_dir: str = "/opt/airflow/dbt/mart",
        dbt_profiles_dir: str = "/opt/airflow/dbt",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.aws_conn_id = aws_conn_id
        self.dbt_command = dbt_command
        self.dbt_target = dbt_target
        self.dbt_vars = dbt_vars or {}
        self.select_models = select_models
        self.data_bucket = data_bucket
        self.dbt_project_dir = dbt_project_dir
        self.dbt_profiles_dir = dbt_profiles_dir

    def execute(self, context: Context) -> str:
        logger.info(f"Starting DBT {self.dbt_command} with target: {self.dbt_target}")

        if self.dbt_target == "local":
            credentials = self._get_local_credentials()
            if self.dbt_command == "run":
                self._cleanup_mart_directory()
        else:
            credentials = self._assume_mart_role()

        dbt_cmd = self._build_dbt_command()
        logger.info(f"Executing DBT command: {' '.join(dbt_cmd)}")

        env = self._build_environment(credentials)

        minutes = 5
        try:
            result = subprocess.run(
                dbt_cmd,
                env=env,
                capture_output=True,
                text=True,
                cwd=self.dbt_project_dir,
                timeout=minutes * 60,
            )

            if result.stdout:
                logger.info(f"DBT stdout:\n{result.stdout}")
            if result.stderr:
                logger.warning(f"DBT stderr:\n{result.stderr}")

            if result.returncode != 0:
                raise AirflowException(
                    f"DBT command failed with return code {result.returncode}:\n"
                    f"STDOUT: {result.stdout}\n"
                    f"STDERR: {result.stderr}"
                )

            logger.info("DBT command completed successfully")
            return result.stdout

        except subprocess.TimeoutExpired:
            raise AirflowException(f"DBT command timed out after {minutes} minutes")
        except Exception as e:
            raise AirflowException(f"Failed to execute DBT command: {str(e)}")

    def _get_local_credentials(self) -> Any:
        """Get credentials for local/localstack environment."""
        hook = AwsBaseHook(aws_conn_id=self.aws_conn_id)
        return hook.get_credentials()

    def _assume_mart_role(self) -> Dict[str, str]:
        """Assume cross-account mart role and return credentials dict."""
        hook = AwsBaseHook(aws_conn_id=self.aws_conn_id)
        session = hook.get_session()
        sts_client = session.client("sts")

        account_id = sts_client.get_caller_identity()["Account"]
        ENVIRONMENT = os.getenv("AIRFLOW_VAR_ENVIRONMENT") or self.dbt_target
        mart_role_arn = (
            f"arn:aws:iam::{account_id}:role/catalunya-mart-role-{ENVIRONMENT}"
        )

        logger.info(f"Assuming mart role: {mart_role_arn}")

        assumed_role = sts_client.assume_role(
            RoleArn=mart_role_arn, RoleSessionName="dbt_execution"
        )

        credentials = assumed_role["Credentials"]
        return {
            "AccessKeyId": credentials["AccessKeyId"],
            "SecretAccessKey": credentials["SecretAccessKey"],
            "SessionToken": credentials["SessionToken"],
        }

    def _get_data_bucket(self) -> str:
        """Get data bucket from parameter or environment variable."""
        bucket = self.data_bucket or os.getenv("DATA_BUCKET")
        if not bucket:
            raise AirflowException(
                "data_bucket must be provided via parameter or DATA_BUCKET env var"
            )
        return bucket

    def _cleanup_mart_directory(self) -> None:
        """Delete mart output directory for local DuckDB runs to allow overwrite."""
        if not self.select_models:
            return

        bucket = self._get_data_bucket()
        prefix = f"marts/{self.select_models}/"

        logger.info(f"Cleaning up mart directory: s3://{bucket}/{prefix}")

        s3 = boto3.client(
            "s3",
            endpoint_url=os.getenv("AWS_ENDPOINT_URL", "http://localstack:4566"),
        )

        paginator = s3.get_paginator("list_objects_v2")
        objects_to_delete = []

        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            if "Contents" in page:
                for obj in page["Contents"]:
                    objects_to_delete.append({"Key": obj["Key"]})

        if not objects_to_delete:
            logger.info(f"No objects to delete in s3://{bucket}/{prefix}")
            return

        for i in range(0, len(objects_to_delete), 1000):
            batch = objects_to_delete[i : i + 1000]
            s3.delete_objects(
                Bucket=bucket,
                Delete={"Objects": batch, "Quiet": True},
            )

        logger.info(
            f"Deleted {len(objects_to_delete)} objects from s3://{bucket}/{prefix}"
        )

    def _build_dbt_command(self) -> List[str]:
        cmd = ["dbt", self.dbt_command]

        # Add target
        cmd.extend(["--target", self.dbt_target])

        # Add profiles directory
        cmd.extend(["--profiles-dir", self.dbt_profiles_dir])

        # Add variables if provided
        if self.dbt_vars:
            import json

            vars_json = json.dumps(self.dbt_vars)
            cmd.extend(["--vars", vars_json])

        # Add model selection if provided
        if self.select_models:
            cmd.extend(["--select", self.select_models])

        return cmd

    def _build_environment(self, credentials) -> Dict[str, str]:
        env = os.environ.copy()

        if isinstance(credentials, dict):
            env["AWS_ACCESS_KEY_ID"] = credentials["AccessKeyId"]
            env["AWS_SECRET_ACCESS_KEY"] = credentials["SecretAccessKey"]
            env["AWS_SESSION_TOKEN"] = credentials["SessionToken"]
        else:
            env["AWS_ACCESS_KEY_ID"] = credentials.access_key
            env["AWS_SECRET_ACCESS_KEY"] = credentials.secret_key
            if credentials.token:
                env["AWS_SESSION_TOKEN"] = credentials.token

        env["AWS_DEFAULT_REGION"] = "eu-west-1"
        env["DBT_TARGET"] = self.dbt_target
        env["DBT_PROJECT_DIR"] = self.dbt_project_dir
        env["DBT_PROFILES_DIR"] = self.dbt_profiles_dir
        env["DATA_BUCKET"] = self._get_data_bucket()

        return env
