import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from airflow.models import BaseOperator
from airflow.providers.amazon.aws.hooks.base_aws import AwsBaseHook


class ObservableBuildDeployOperator(BaseOperator):
    template_fields = ('environment', 'bucket_name', 'repository_url', 'branch')

    ui_color = '#ff9900'
    ui_fgcolor = '#ffffff'

    def __init__(
            self,
            *,
            repository_url: str,
            bucket_name: str,
            environment: str = 'dev',
            branch: Optional[str] = None,
            s3_prefix: str = 'dataservice/observable',
            aws_conn_id: str = 'aws_default',
            region: str = 'eu-west-1',
            **kwargs
    ):
        super().__init__(**kwargs)
        self.repository_url = repository_url
        self.bucket_name = bucket_name
        self.environment = environment
        self.branch = branch or ('main' if environment == 'prod' else 'develop')
        self.s3_prefix = s3_prefix
        self.aws_conn_id = aws_conn_id
        self.region = region
        self.s3_bucket_data = f'catalunya-data-{environment}'
        self.s3_bucket_catalog = f'catalunya-catalog-{environment}'

    def execute(self, context):
        self.log.info(f"🚀 Starting Observable build and deploy for {self.environment}")
        self.log.info(f"   Repository: {self.repository_url}")
        self.log.info(f"   Branch: {self.branch}")
        self.log.info(f"   Target: s3://{self.bucket_name}/{self.s3_prefix}")

        tmp_dir = tempfile.mkdtemp(prefix='observable-build-')

        try:
            zip_path = os.path.join(tmp_dir, 'repo.zip')
            download_url = f"{self.repository_url}/archive/refs/heads/{self.branch}.zip"

            self.log.info(f"📥 Downloading repository from {download_url}")
            subprocess.run(
                ['curl', '-L', download_url, '-o', zip_path],
                check=True,
                capture_output=True
            )

            self.log.info("📦 Extracting repository...")
            subprocess.run(
                ['unzip', '-q', zip_path, '-d', tmp_dir],
                check=True,
                capture_output=True
            )

            observable_dir = os.path.join(tmp_dir, f'CloudGentGran-{self.branch}', 'observable')

            if not os.path.exists(observable_dir):
                raise FileNotFoundError(f"Observable directory not found at {observable_dir}")

            self.log.info(f"📂 Found observable directory at {observable_dir}")

            self.log.info("📦 Running npm ci...")
            npm_ci_result = subprocess.run(
                ['npm', 'ci'],
                cwd=observable_dir,
                check=True,
                capture_output=True,
                text=True
            )
            if npm_ci_result.stdout:
                self.log.info(f"npm ci stdout:\n{npm_ci_result.stdout}")
            if npm_ci_result.stderr:
                self.log.warning(f"npm ci stderr:\n{npm_ci_result.stderr}")

            self.log.info("🔨 Running npm run build...")

            hook = AwsBaseHook(aws_conn_id=self.aws_conn_id, client_type='s3')
            session = hook.get_session()
            sts_client = session.client('sts')

            account_id = sts_client.get_caller_identity()['Account']

            ENVIRONMENT = os.getenv('AIRFLOW_VAR_ENVIRONMENT')
            dataservice_role_arn = f"arn:aws:iam::{account_id}:role/catalunya-data-service-role-{ENVIRONMENT}"

            self.log.info(f"Assuming dataservice role: {dataservice_role_arn}")
            assumed_role = sts_client.assume_role(
                RoleArn=dataservice_role_arn,
                RoleSessionName='observable_build'
            )
            credentials = assumed_role['Credentials']

            env = os.environ.copy()
            node_bin_path = os.path.join(observable_dir, 'node_modules', '.bin')
            env['PATH'] = f"{node_bin_path}:{env.get('PATH', '')}"
            env['S3_BUCKET_DATA'] = self.s3_bucket_data
            env['S3_BUCKET_CATALOG'] = self.s3_bucket_catalog

            # Add AWS credentials instead of AWS_PROFILE
            env['AWS_ACCESS_KEY_ID'] = credentials['AccessKeyId']
            env['AWS_SECRET_ACCESS_KEY'] = credentials['SecretAccessKey']
            env['AWS_SESSION_TOKEN'] = credentials['SessionToken']
            env['AWS_REGION'] = self.region
            env['AWS_DEFAULT_REGION'] = self.region
            env['AWS_ENDPOINT_URL'] = os.getenv('AWS_ENDPOINT_URL', '')


            result = subprocess.run(
                ['npm', 'run', 'build'],
                cwd=observable_dir,
                check=True,
                capture_output=True,
                text=True,
                env=env
            )

            # Log build output
            if result.stdout:
                self.log.info(f"Build stdout:\n{result.stdout}")
            if result.stderr:
                self.log.warning(f"Build stderr:\n{result.stderr}")

            self.log.info(f"Build output:\n{result.stdout}")

            build_dir = os.path.join(observable_dir, 'dist')
            if not os.path.exists(build_dir):
                raise FileNotFoundError(f"Build output not found at {build_dir}")

            self.log.info(f"☁️  Uploading to S3: s3://{self.bucket_name}/{self.s3_prefix}")
            uploaded_files = self._upload_directory_to_s3(build_dir)

            self.log.info(f"✅ Successfully uploaded {len(uploaded_files)} files")

            return {
                'status': 'success',
                'bucket': self.bucket_name,
                'prefix': self.s3_prefix,
                'files_uploaded': len(uploaded_files),
                'branch': self.branch,
                'environment': self.environment
            }

        except subprocess.CalledProcessError as e:
            self.log.error(f"❌ Command failed: {e.cmd}")
            self.log.error(f"   stdout: {e.stdout}")
            self.log.error(f"   stderr: {e.stderr}")
            raise
        except Exception as e:
            self.log.error(f"❌ Build failed: {str(e)}")
            raise
        finally:
            self.log.info(f"🧹 Cleaning up temporary directory: {tmp_dir}")
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _upload_directory_to_s3(self, directory: str) -> list:
        aws_hook = AwsBaseHook(aws_conn_id=self.aws_conn_id, client_type='s3')
        s3_client = aws_hook.get_conn()

        uploaded_files = []
        dir_path = Path(directory)

        for file_path in dir_path.rglob('*'):
            if file_path.is_file():
                relative_path = file_path.relative_to(dir_path)
                s3_key = f"{self.s3_prefix}/{relative_path.as_posix()}"

                self.log.info(f"   Uploading {relative_path} → {s3_key}")

                s3_client.upload_file(
                    str(file_path),
                    self.bucket_name,
                    s3_key
                )
                uploaded_files.append(s3_key)

        return uploaded_files