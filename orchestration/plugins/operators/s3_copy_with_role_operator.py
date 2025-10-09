import os
import logging

from airflow.models import BaseOperator
from airflow.providers.amazon.aws.hooks.base_aws import AwsBaseHook
from airflow.utils.context import Context
from airflow.exceptions import AirflowException
import ast
logger = logging.getLogger(__name__)


class S3CopyWithRoleOperator(BaseOperator):
    template_fields = ['source_bucket_key', 'dest_bucket_key']

    def __init__(
            self,
            aws_conn_id: str,
            role_type: str,
            source_bucket_name: str,
            source_bucket_key: str,
            dest_bucket_name: str,
            dest_bucket_key: str,
            **kwargs
    ):
        super().__init__(**kwargs)
        self.aws_conn_id = aws_conn_id
        self.role_type = role_type
        self.source_bucket_name = source_bucket_name
        self.source_bucket_key = source_bucket_key
        self.dest_bucket_name = dest_bucket_name
        self.dest_bucket_key = dest_bucket_key

    def execute(self, context: Context) -> list[str]:
        logger.info(f"S3 copy operation using {self.role_type} role")
        logger.info(f"Source: s3://{self.source_bucket_name}/{self.source_bucket_key}")
        logger.info(f"Destination: s3://{self.dest_bucket_name}/{self.dest_bucket_key}")
        if isinstance(self.source_bucket_key, str) and not self.source_bucket_key.startswith('{{'):
            self.source_bucket_key = ast.literal_eval(self.source_bucket_key)
        if isinstance(self.dest_bucket_key, str) and not self.dest_bucket_key.startswith('{{'):
            self.dest_bucket_key = ast.literal_eval(self.dest_bucket_key)
        logger.info(f"Parsing Source: s3://{self.source_bucket_name}/{self.source_bucket_key}")
        logger.info(f"Parsing Destination: s3://{self.dest_bucket_name}/{self.dest_bucket_key}")

        hook = AwsBaseHook(aws_conn_id=self.aws_conn_id)
        session = hook.get_session()
        sts_client = session.client('sts')

        account_id = sts_client.get_caller_identity()['Account']

        ENVIRONMENT = os.getenv('AIRFLOW_VAR_ENVIRONMENT')
        role_arn = f"arn:aws:iam::{account_id}:role/catalunya-{self.role_type}-role-{ENVIRONMENT}"

        logger.info(f"Assuming role: {role_arn}")

        assumed_role = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName=f's3_copy_{self.role_type}'
        )

        credentials = assumed_role['Credentials']

        s3_client = session.client(
            's3',
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken']
        )

        try:
            for source_bucket_key, dest_bucket_key in zip(self.source_bucket_key, self.dest_bucket_key):
                copy_source = {
                    'Bucket': self.source_bucket_name,
                    'Key': source_bucket_key
                }

                s3_client.copy_object(
                    CopySource=copy_source,
                    Bucket=self.dest_bucket_name,
                    Key=dest_bucket_key
                )

                logger.info(f"Successfully copied object to s3://{self.dest_bucket_name}/{dest_bucket_key}")

            return self.dest_bucket_key

        except Exception as e:
            raise AirflowException(f"Failed to copy S3 object: {str(e)}")