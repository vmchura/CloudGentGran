# Apache Airflow Orchestration

This folder contains Apache Airflow DAGs that orchestrate the Catalunya data pipeline, coordinating Lambda functions, S3 operations, and dbt transformations.

## Overview

The orchestration layer manages the end-to-end data pipeline execution:

```
Extractors → Transformers → Marts → dbt Models
    ↓          ↓            ↓
   S3         S3          S3/Athena
```

Airflow runs on Dokku (on-premise) in both development and production environments, coordinating AWS Lambda functions across accounts via cross-account IAM roles.

## Environment Configuration

DAGs read environment configuration from Airflow Variables:

| Environment | Variable | Airflow Connection |
|-------------|-----------|-------------------|
| local | `environment=local` | `localstack_default` |
| dev | `environment=dev` | `aws_cross_account_role` |
| prod | `environment=prod` | `aws_cross_account_role` |

## DAGs

### 1. catalunya_catalog_initializer.py
Initializes the data catalog with static reference data.

**Pipeline:**
1. Invoke `service_type_initializer` Lambda
2. Invoke `service_qualification_initializer` Lambda
3. Invoke `municipals_initializer` Lambda

**Output:**
- `service_type.parquet`: 59 service type definitions
- `service_qualification.parquet`: 3 qualification types
- `municipals.parquet`: Municipality and comarca mappings

**Environment:** All (local/dev/prod)

### 2. catalunya_social_services_dag.py
Processes daily social services data from Catalunya Open Data.

**Pipeline:**
1. Invoke `social_services_extractor` Lambda
2. Parse extractor response for S3 keys
3. Invoke `social_services_transformer` Lambda
4. Run `social_services_staging` dbt model

**Schedule:** Daily (configurable via Airflow)

**Output:**
- `staging/social_services/downloaded_date={YYYYMMDD}/social_services.parquet`
- Glue partitions added automatically

### 3. catalunya_long_term_update.py
Manually triggers population data update from IDESCAT census API.

**Pipeline:**
1. Invoke `population_municipal_greater_65_initializer` Lambda
2. Prepare transformer payload from extractor response
3. Invoke `population_municipal_greater_65_transformer` Lambda
4. Prepare mart payload from transformer response
5. Invoke `population_municipal_greater_65_mart` Lambda
6. Validate mart completion
7. Run `comarca_population` dbt model

**Schedule:** None (manual trigger only)
- Tag: `manual` for easy identification

**Configuration:**
- Retry attempts: 1
- Retry delay: 10 minutes
- Timeout: 10 minutes per task

### 4. catalunya_comarques_boundaries_dag.py
Updates geographical boundaries for comarques and municipalities from ICGC.

**Pipeline:**
1. Invoke `comarques_boundaries_extractor` Lambda
2. Parse extractor response for GeoJSON S3 keys
3. Copy to staging using `S3CopyWithRoleOperator` (transformer role)
4. Copy to marts using `S3CopyWithRoleOperator` (mart role)

**Schedule:** None (manual trigger only)
- Tag: `manual` for easy identification

**Output:**
- `staging/comarques-boundaries/comarques-1000000.json`
- `staging/comarques-boundaries/municipis-1000000.json`
- `marts/comarques-boundaries/comarques-1000000.json`
- `marts/comarques-boundaries/municipis-1000000.json`

### 5. standalone_observable.py
Triggers the observable data service build for public dashboards.

**Pipeline:**
1. Runs dbt models to create service layer data
2. Triggers Observable Framework build process
3. Deploys static site to S3/CloudFront

**Schedule:** Manual trigger only

## Custom Operators

### DbtAthenaOperator
Location: `operators/dbt_athena_operator.py`

Runs dbt commands against Athena database.

**Parameters:**
- `aws_conn_id`: AWS connection name
- `dbt_command`: Command to run (run, test, etc.)
- `dbt_target`: Target environment (local/dev/prod)
- `select_models`: Optional model selection

**Usage:**
```python
DbtAthenaOperator(
    task_id='run_model',
    aws_conn_id='aws_cross_account_role',
    dbt_command='run',
    dbt_target=ENVIRONMENT,
    select_models='comarca_population',
    dag=dag
)
```

### S3CopyWithRoleOperator
Location: `operators/s3_copy_with_role_operator.py`

Performs S3 copy operations using specific IAM roles.

**Parameters:**
- `aws_conn_id`: AWS connection name
- `role_type`: IAM role to use (extractor/transformer/mart)
- `source_bucket_name`: Source S3 bucket
- `source_bucket_key`: Source S3 key(s) (supports list)
- `dest_bucket_name`: Destination S3 bucket
- `dest_bucket_key`: Destination S3 key(s) (supports list)

**Usage:**
```python
S3CopyWithRoleOperator(
    task_id='copy_to_staging',
    aws_conn_id='aws_cross_account_role',
    role_type='transformer',
    source_bucket_name='catalunya-data-dev',
    source_bucket_key=['landing/file1.json', 'landing/file2.json'],
    dest_bucket_name='catalunya-data-dev',
    dest_bucket_key=['staging/file1.json', 'staging/file2.json'],
    dag=dag
)
```

**Supported Roles:**
- `extractor`: Reads from landing, writes to staging
- `transformer`: Reads from staging, writes to marts
- `mart`: Reads from marts, writes to service layer

## Lambda Function Naming Convention

Functions follow the pattern: `{prefix}-{environment}-{function_name}`

Examples:
- `catalunya-dev-social_services_extractor`
- `catalunya-prod-population_municipal_greater_65_transformer`
- `catalunya-dev-comarques_boundaries`

## Cross-Account IAM Pattern

Airflow assumes roles in the target AWS account:

1. **Airflow Assumer User**: Minimal permissions, only can assume target roles
   - Access key and secret stored in Airflow connection
   - External ID: `catalunya-{environment}-airflow-exec`

2. **Airflow Target Role**: Cross-account role with Lambda execution permissions
   - Assumed by Airflow user
   - Used to invoke Lambda functions
   - Scoped to specific resources

## Error Handling

All DAGs implement:
- **Email on failure**: Notifications to configured recipients
- **Retry logic**: Configurable retry attempts with exponential backoff
- **XCom validation**: Tasks validate upstream task responses before proceeding
- **AirflowException**: Raises exceptions on validation failures

## XCom Data Flow

DAGs use XCom to pass data between tasks:

```python
# Extractor response
{
  "success": true,
  "data": {
    "bucket": "catalunya-data-dev",
    "semantic_identifier": "social_services",
    "downloaded_date": "20240101",
    "total_records": 5000,
    "s3_keys": [...]
  }
}

# Transformer payload
{
  "source_prefix": "landing/social_services/downloaded_date=20240101/"
}
```

## DAG Execution Flow

### Social Services Pipeline

```
social_services_extractor
    ↓ (XCom: s3_keys, downloaded_date)
prepare_transformer_payload
    ↓ (XCom: source_prefix)
social_services_transformer
    ↓
social_services_staging (dbt)
```

### Population Pipeline

```
population_municipal_greater_65_initializer
    ↓ (XCom: semantic_identifier)
prepare_transformer_payload
    ↓ (XCom: source_prefix)
population_municipal_greater_65_transformer
    ↓ (XCom: target_prefix)
prepare_mart_payload
    ↓ (XCom: source_prefix)
population_municipal_greater_65_mart
    ↓ (XCom: status, target_prefix)
validate_mart
    ↓
comarca_population (dbt)
```

## Deployment

### Authentication

Airflow 3.x uses SimpleAuthManager for authentication:

**Local Development:**
- No authentication required (`SIMPLE_AUTH_MANAGER_ALL_ADMINS=true`)
- Direct access to Airflow UI at http://localhost:8080

**Production:**
- SimpleAuthManager auto-generates passwords on first start
- Passwords are stored in `$AIRFLOW_HOME/simple_auth_manager_passwords.json.generated`
- To set a fixed password, use the `AIRFLOW_ADMIN_PASSWORD` environment variable:
  ```bash
  dokku config:set <app-name> AIRFLOW_ADMIN_PASSWORD='your_secure_password'
  ```
- Note: SimpleAuthManager is intended for development. For production, ensure access is controlled through other means (network security, reverse proxy auth, etc.)

### Git-Sync Architecture

The container fetches dbt models, DAGs, plugins, and config from the Git repository at startup using git-sync:

```
Container Start
      ↓
git-sync fetches from GitHub (sparse checkout)
      ↓
setup-links.sh creates symlinks
      ↓
/opt/airflow/dbt → /git-sync/repo/dbt
/opt/airflow/dags → /git-sync/repo/orchestration/dags
/opt/airflow/plugins → /git-sync/repo/orchestration/plugins
/opt/airflow/config → /git-sync/repo/orchestration/config
      ↓
Airflow starts with fresh content
```

**Branch Selection:**
- Production: `main`
- Development/Local: `develop`

**Manual Re-sync:**
To update content without redeploying:
```bash
dokku run <app-name> /opt/airflow/scripts/sync-repo.sh
```

### Local Development

Build and run the Docker image locally:
With the script of local deployment

### Production

Deployed to Dokku on-premise server via:

```bash
./scripts/deploy/deploy-orchestration.sh <environment> <dokku-server> <ssh-key> <domain>
```

### Post-Deployment Steps (First Deployment Only)

After the first deployment, you must configure the following:

1. **Generate and set Fernet key** (required for Airflow to encrypt sensitive data):
   ```bash
   dokku config:set <app-name> AIRFLOW__CORE__FERNET_KEY=$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')
   ```

2. **Set admin password**:
   ```bash
   dokku config:set <app-name> AIRFLOW_ADMIN_PASSWORD='your_secure_password'
   ```

3. **Set AWS credentials and connection** (from `extract_aws_credentials.sh` output):
   ```bash
   dokku run <app-name> airflow connections add aws_cross_account_role ...
   dokku config:set <app-name> AWS_ACCESS_KEY_ID='...' AWS_SECRET_ACCESS_KEY='...' AWS_DEFAULT_REGION='...'
   ```

4. **Restart the app** after setting variables:
   ```bash
   dokku ps:restart <app-name>
   ```

## Monitoring

- **Airflow Web UI**: View DAG runs, task status, logs
- **CloudWatch Logs**: Lambda function logs streamed to CloudWatch
- **Airflow Email**: Failure notifications sent to configured emails

## Configuration Files

- **DAG definitions**: `dags/*.py`
- **Custom operators**: `operators/*.py`
- **Airflow configuration**: `airflow.cfg` (in Docker Compose)
- **Connections**: Configured via Airflow Web UI
- **Variables**: Configured via Airflow Web UI (`environment` variable required)

## Common Patterns

### 1. Parse Lambda Response

```python
def parse_extractor_response(**context):
    task_instance = context['task_instance']
    response = task_instance.xcom_pull(task_ids='lambda_task')
    response = json.loads(response) if isinstance(response, str) else response

    if not response or not response.get('success'):
        raise AirflowException("Extractor failed")

    return {'source_prefix': response['data']['source_prefix']}
```

### 2. XCom Parameter Passing

```python
# Pass XCom to next task
payload="{{ task_instance.xcom_pull(task_ids='prepare_payload') | tojson }}"

# Use in Python task
def process_data(**context):
    payload = context['task_instance'].xcom_pull(task_ids='prepare_payload')
```

### 3. Task Dependencies

```python
# Linear chain
task1 >> task2 >> task3

# Branching
task1 >> [task2a, task2b] >> task3
```
