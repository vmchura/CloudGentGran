# AGENTS.md - Catalunya Data Pipeline Development Guide

This document provides coding guidelines, build/test commands, and conventions for AI coding agents working on this repository.

---

## Build Commands

### Infrastructure (CDK/TypeScript)

```bash
cd infrastructure

# Build TypeScript
npm run build

# Watch for changes (development)
npm run watch

# Run tests
npm test

# Deploy to AWS
npx cdk deploy CatalunyaDataStack-dev
npx cdk deploy CatalunyaDataStack-prod

# Local development (LocalStack)
npx cdk deploy CatalunyaDataStack-dev --context localstack=true

# Synthesize only (no deploy)
npx cdk synth

# Bootstrap CDK (first time)
npx cdk bootstrap
```

### Python Lambda Functions

```bash
cd lambda/extractors/<function_name>

# Install dependencies (if new)
pip install -r requirements.txt

# Run unit tests
python -m unittest test_<function_name>.py

# Test single function
python -m unittest test_<function_name>.py TestClassName.test_method_name

# LocalStack testing with LocalStack running
AWS_ENDPOINT_URL=http://localhost:4566 python -m lambda lambda_function
```

### Rust Lambda Functions

```bash
cd lambda/transformers/<function_name>/

# Build for production
cargo lambda build --release --target x86_64-unknown-linux-gnu

# Build for local testing
cargo lambda build

# Run unit tests
cargo test

# Run single test
cargo test test_name

# Local testing with Cargo Lambda
cargo lambda watch
cargo lambda invoke --data-ascii '{"key":"value"}' --remote -p localstack --endpoint-url http://localhost:4566

# Deploy individual lambda (not recommended for production)
cargo lambda deploy --function-name <name>

# Format code
cargo fmt
```

### dbt Models

```bash
cd dbt/mart

# Run all models
dbt run

# Run specific model
dbt run --select comarca_population

# Run tests
dbt test

# Generate documentation
dbt docs generate

# Run with specific environment variable
DATA_BUCKET=catalunya-data-dev dbt run --target dev
```

### Airflow DAGs

```bash
cd orchestration

# Trigger specific DAG
airflow dags trigger catalunya_social_services_pipeline

# Test DAG syntax
python -m py_compile dags/catalunya_social_services_dag.py

# Clear DAG state
airflow dags clear catalunya_social_services_pipeline

# Unpause DAG
airflow dags unpause catalunya_social_services_pipeline

# List DAGs
airflow dags list
```

---

## Code Style Guidelines

### Python (Extractors, Orchestration)

#### Imports

Order: standard library → third-party → local modules

```python
# Standard library first
import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional, List

# Third-party libraries
import boto3
import pandas as pd
from botocore.exceptions import ClientError, NoCredentialsError

# Local project modules (using absolute imports from lambda root)
from common.exceptions import (
    LambdaError,
    ConfigurationError,
    APIError,
    ERROR_STATUS_CODES,
    get_current_time,
)
```

#### Type Annotations

**Required** for all function signatures and return types:

```python
def validate_environment() -> tuple[str, str]:
    """Validate required environment variables"""

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main Lambda handler function"""

def upload_to_s3(bucket_name: str, data: bytes, key: str) -> str:
    """Upload extracted data to S3"""
```

#### Naming Conventions

- **Files**: `snake_case.py` (e.g., `api_extractor.py`, `s3_copy_with_role_operator.py`)
- **Classes**: `PascalCase` (e.g., `TestSocialServicesApiExtractor`, `S3CopyWithRoleOperator`)
- **Functions**: `snake_case` (e.g., `lambda_handler`, `create_response`, `get_s3_client`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `ERROR_STATUS_CODES`, `MAX_RETRIES`)
- **Private methods**: `_leading_underscore` (internal use only)

#### Error Handling

Use custom exceptions from `lambda/common/exceptions.py`:

```python
# Import base exceptions
from common.exceptions import (
    LambdaError,
    ConfigurationError,
    APIError,
    DataValidationError,
    DataProcessingError,
    S3OperationError,
    ERROR_STATUS_CODES,
)

# Raise specific exceptions
raise ConfigurationError(
    f"Missing required environment variables: {', '.join(missing_vars)}"
)

# Handle specific exceptions
except (ConfigurationError, APIError) as e:
    logger.error(f"Configuration error: {str(e)}")
    return create_response(False, str(e), error_type="ConfigurationError")

# Map exceptions to HTTP status codes via ERROR_STATUS_CODES
if error_type:
    status_code = ERROR_STATUS_CODE_NAMES.get(error_type, 500)
```

#### Logging

```python
logger = logging.getLogger(__name__)

# Info level
logger.info(f"Processing {len(records)} records")

# Warning level
logger.warning(f"Low record count: {count} < {expected}")

# Error level
logger.error(f"Failed to upload: {str(e)}")

# Include context
logger.info(f"Processing file: {filename} for date: {downloaded_date}")
```

#### DataFrames (Pandas)

```python
# Column selection
df = df[['column1', 'column2', 'column3']]

# Rename columns with mapping
column_mapping = {'old_name': 'new_name', 'another': 'new_another'}
df = df.rename(columns=column_mapping)

# Filter
filtered_df = df[df['column'] > threshold]

# Type conversion
df['date_column'] = pd.to_datetime(df['date_column'])
df['numeric_column'] = df['string_column'].astype('Int64')

# Handle nulls
df['column'] = df['column'].fillna('default_value')
```

---

### Rust (Transformers, Marts)

#### Entry Point

Lambda functions use `bootstrap` as entry point (handled by `lambda_runtime`):

```rust
use lambda_runtime::{service_fn, LambdaEvent};
use serde::{Deserialize, Serialize};
use serde_json::json;

#[derive(Deserialize)]
struct LambdaInput {
    source_prefix: String,
}

#[derive(Serialize)]
struct LambdaOutput {
    status: String,
    target_prefix: Option<String>,
}

#[service_fn(lambda_handler)]
pub async fn function_handler(event: LambdaEvent<LambdaInput>) -> Result<LambdaOutput, Error> {
    // Handler implementation
}
```

#### Naming Conventions

- **Files**: `snake_case` (e.g., `main.rs`, `generic_handler.rs`)
- **Modules**: `snake_case` (e.g., `mod generic_handler;`)
- **Structs**: `PascalCase` (e.g., `LambdaInput`, `LambdaOutput`, `ProcessingResult`)
- **Functions**: `snake_case` (e.g., `function_handler`, `upload_to_s3`, `process_data`)
- **Constants**: `SCREAMING_SNAKE_CASE` (e.g., `MAX_RETRIES`, `BUFFER_SIZE`)
- **Macros**: `snake_case!` for macros

#### Error Handling

Use `anyhow::Result<T>` for fallible operations:

```rust
use anyhow::{anyhow, Result};
use aws_sdk_s3::Client;

async fn upload_parquet_to_s3(
    s3_client: &Client,
    df: &DataFrame,
    bucket: &str,
    s3_key: &str,
) -> Result<()> {
    s3_client.put_object()
        .bucket(bucket)
        .key(s3_key)
        .body(ByteStream::from(buf))
        .send()
        .await
        .map_err(|e| anyhow!("S3 upload failed: {}", e))?;
    
    Ok(())
}

// Function returning Result
fn process_data(input: &str) -> Result<DataFrame> {
    if input.is_empty() {
        return Err(anyhow!("Input is empty"));
    }
    // Processing logic
    Ok(dataframe)
}
```

#### Async Runtime

```rust
use tokio::time::{sleep, Duration};

// Async function with tokio
pub async fn function_handler(event: LambdaEvent<LambdaInput>) -> Result<LambdaOutput, Error> {
    // Async operation
    sleep(Duration::from_secs(3)).await;
    
    Ok(LambdaOutput {
        status: "succeeded".to_string(),
        target_prefix: Some(target_key),
    })
}

// Tokio runtime with main
#[tokio::main]
async fn main() -> Result<(), Error> {
    lambda_runtime::run(service_fn(function_handler)).await
}
```

#### Polars DataFrame Operations

```rust
use polars::prelude::*;

// Read JSON to DataFrame
let df = JsonReader::new(cursor).finish()?;

// Select columns
let df = df.select([
    col("registre"),
    col("tipologia"),
    col("capacitat"),
])?;

// Filter
let df = df.filter(col("capacitat").gt(lit(0)))?;

// Lazy evaluation for performance
let lazy_df = df.lazy()
    .with_columns([
        when(col("qualificacio").eq(lit("null"))
            .then(lit(NULL))
            .otherwise(col("qualificacio"))
            .alias("qualificacio"),
    ])
    .collect()?;

// Join
let df = df.join(
    &service_types_df,
    ["tipologia"],
    ["service_type_description"],
    JoinArgs::new(JoinType::Left),
    None,
)?;

// Sort and deduplicate
let df = df.sort(
    ["registre", "tokens_similar"],
    SortMultipleOptions::default().with_order_descending_multi([false, true]),
)?.unique(
    Some(&["registre", "inscripcio"]),
    UniqueKeepStrategy::First,
    None,
)?;

// Type casting
let df = df.lazy()
    .with_columns([
        col("capacitat").cast(DataType::Int32).alias("capacity"),
        col("inscripcio").str().to_date(StrptimeOptions {
            format: Some("%Y-%m-%d".into()),
            ..Default::default()
        }).alias("inscription_date"),
    ])
    .collect()?;
```

#### Workspace Dependencies

All Rust lambdas use workspace dependencies from top-level `lambda/Cargo.toml`:

```toml
[workspace.dependencies]
lambda_runtime.workspace = true  # Runtime library
serde.workspace = true            # Serialization
tokio.workspace = true             # Async runtime
polars.workspace = true            # DataFrame processing
anyhow.workspace = true            # Error handling
```

---

### TypeScript (CDK Infrastructure)

#### Type Safety

```typescript
// Strict mode enabled in tsconfig.json
"strict": true,
"noImplicitAny": true,
"strictNullChecks": true,
"noImplicitReturns": true,

// Interface for props
export interface LambdaConstructProps {
    environmentName: string;
    projectName: string;
    config: EnvironmentConfig;
    bucketName: string;
    catalogBucketName: string;
    lambdaPrefix: string;
    account: string;
    region: string;
    executionRole: iam.Role;
}

// Optional properties
export interface EnvironmentConfig {
    region: string;
    bucketName: string;
    lambdaMemory: number;
    lambdaTimeout: number;
    retentionPeriod: number;
    scheduleCron: string;
    catalogBucketName: string;
    requireMfaForHumanRoles?: boolean;  // Optional
    webDomain: string;
    webSubdomain?: string;  // Optional
}
```

#### Naming Conventions

- **Interfaces**: `PascalCase` ending in `Props` (e.g., `LambdaConstructProps`, `EnvironmentConfig`)
- **Classes**: `PascalCase` ending in `Construct` (e.g., `LambdaConstruct`, `S3Construct`, `AnalyticsConstruct`)
- **Methods**: `camelCase` (e.g., `getEnvironmentConfig`, `getResourceName`, `getCommonTags`)
- **Properties**: `camelCase` (private) or `public readonly` fields
- **Constants**: `PascalCase` (e.g., `ProjectName`, `EnvironmentName`)
- **Construct IDs**: `PascalCase` (e.g., `CatalunyaDataStack`, `TestDevStack`)

#### AWS CDK Patterns

```typescript
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';

// Constructor
export class LambdaConstruct extends Construct {
    public readonly apiExtractorLambda: lambda.Function;
    public readonly socialServicesTransformerLambda: lambda.Function;

    constructor(scope: Construct, id: string, props: LambdaConstructProps) {
        super(scope, id);

        const {
            environmentName,
            projectName,
            config,
            bucketName,
            lambdaPrefix,
            account,
            region,
        } = props;  // Destructure props

        // Create resources
        this.apiExtractorLambda = new lambda.Function(this, 'ApiExtractorLambda', {
            functionName: `${lambdaPrefix}-social_services`,
            runtime: lambda.Runtime.PYTHON_3_13,
            handler: 'api_extractor.lambda_handler',
            code: this.getPythonLambdaCode('social_services'),
            timeout: cdk.Duration.seconds(config.lambdaTimeout),
            memorySize: config.lambdaMemory,
            role: props.executionRole,
            environment: {
                BUCKET_NAME: bucketName,
                SEMANTIC_IDENTIFIER: 'social_services',
                DATASET_IDENTIFIER: 'ivft-vegh',
                ENVIRONMENT: environmentName,
                REGION: region
            },
        });

        // Add tags
        const commonTags = ConfigHelper.getCommonTags(environmentName);
        Object.entries(commonTags).forEach(([key, value]) => {
            cdk.Tags.of(apiExtractorLambda).add(key, value);
        });
    }
}

// Static methods for helpers
export class ConfigHelper {
    public static getEnvironmentConfig(scope: Construct, environmentName: string): EnvironmentConfig {
        const projectConfig = scope.node.tryGetContext('Catalunya-Data-Pipeline');
        if (!projectConfig) {
            throw new Error(`No 'Catalunya-Data-Pipeline' configuration found`);
        }
        const config = projectConfig[environmentName];
        return { /* config object */ };
    }

    public static validateEnvironment(environmentName: string): void {
        const validEnvironments = ['dev', 'prod'];
        if (!validEnvironments.includes(environmentName)) {
            throw new Error(`Invalid environment: ${environmentName}`);
        }
    }

    public static getResourceName(baseName: string, environmentName: string): string {
        return `${baseName}-${environmentName}`;
    }

    public static getCommonTags(environmentName: string): Record<string, string> {
        return {
            Project: 'CatalunyaDataPipeline',
            Environment: environmentName,
            Owner: 'CloudGentGran',
        };
    }
}
```

#### Resource Naming

```typescript
// Lambda functions: `{lambdaPrefix}-{function_name}`
functionName: `${lambdaPrefix}-social_services`
functionName: `${lambdaPrefix}-population_municipal_greater_65`

// IAM roles: `catalunya-{layer}-role-{environment}`
extractor: `catalunya-lambda-extractor-role-${environmentName}`
transformer: `catalunya-lambda-transformer-role-${environmentName}`
mart: `catalunya-mart-role-${environmentName}`

// S3 buckets: `catalunya-{type}-{environmentName}`
data: `catalunya-data-${environmentName}`
catalog: `catalunya-catalog-${environmentName}`
service: `catalunya-service-${environmentName}`

// Athena: `catalunya_data_{environmentName}`
athenaDatabaseName: `catalunya_data_${environmentName}`
athenaWorkgroupName: `catalunya-workgroup-${environmentName}`
```

#### CloudFormation Outputs

```typescript
// Export outputs for cross-stack reference
new cdk.CfnOutput(this, 'BucketName', {
    value: this.bucketName,
    description: 'S3 bucket name for data storage',
    exportName: `${projectName}-BucketName`,
});

new cdk.CfnOutput(this, 'ExtractorRoleArn', {
    value: this.iamInfrastructure.extractorExecutionRole.roleArn,
    description: 'Lambda extractor execution role ARN',
    exportName: `${projectName}-ExtractorRoleArn`,
});
```

---

### SQL (dbt Models)

#### Formatting

```sql
-- Uppercase keywords, lowercase column names
SELECT
    comarca_id,
    SUM(capacity) as total_capacity
FROM staging_data
GROUP BY comarca_id

-- 2-space indentation (no tabs)
  WITH cte AS (
    SELECT column1, column2 FROM table
  )
  SELECT * FROM cte

-- Line breaks before major clauses
SELECT
    column1,
    column2
FROM table1
JOIN table2 ON table1.id = table2.id
WHERE condition
```

#### CTEs (Common Table Expressions)

```sql
WITH population_with_comarca AS (
  SELECT
    p.population_age_65_and_over,
    p.population,
    p.year,
    m.comarca_id
  FROM municipal_population p
  JOIN municipals m
    ON p.municipal_id = m.municipal_id
),
comarca_population_aggregated AS (
  SELECT
    p.comarca_id,
    SUM(p.population_age_65_and_over) as population_age_65_and_over,
    SUM(p.population) as population
  FROM population_with_comarca p
  GROUP BY p.comarca_id, p.year
)
SELECT * FROM comarca_population_aggregated
```

#### Jinja Macros (dbt)

```sql
-- Use adapter_aware_table_config for different databases
{{ adapter_aware_table_config() }}

-- Use read_staging_data macro
FROM {{ read_staging_data('social_services', 'downloaded_date', var('downloaded_date')) }}

-- Use read_catalog_data macro
JOIN {{ read_catalog_data('municipals') }} m
  ON data.municipal_id = m.municipal_id

-- Environment variables via env_var()
location = "s3://{{ env_var('DATA_BUCKET') }}/marts/{{ this.name }}"

-- Conditional config
{% if target.type == 'duckdb' %}
  {{ config(materialized = 'external', format = 'parquet') }}
{% else %}
  {{ config(materialized = 'table') }}
{% endif %}

-- Loop over values
{% for year in generate_years() %}
  WHERE year = '{{ year }}'
{% endfor %}
```

---

### Airflow DAGs and Operators

#### Operator Pattern

```python
from airflow.models import BaseOperator
from airflow.utils.context import Context
from airflow.exceptions import AirflowException
import ast
import logging

logger = logging.getLogger(__name__)

class CustomOperator(BaseOperator):
    # Template fields for Jinja support
    template_fields = ['source_bucket_key', 'dest_bucket_key']

    def __init__(
        self,
        aws_conn_id: str,
        role_type: str,
        source_bucket_name: str,
        source_bucket_key: str,
        dest_bucket_name: str,
        dest_bucket_key: str,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.aws_conn_id = aws_conn_id
        self.role_type = role_type
        self.source_bucket_name = source_bucket_name
        self.source_bucket_key = source_bucket_key
        self.dest_bucket_name = dest_bucket_name
        self.dest_bucket_key = dest_bucket_key

    def execute(self, context: Context) -> list[str]:
        logger.info(f"Starting S3 copy using {self.role_type} role")

        # Parse Jinja templates using ast.literal_eval()
        if isinstance(self.source_bucket_key, str) and not self.source_bucket_key.startswith('{{'):
            self.source_bucket_key = ast.literal_eval(self.source_bucket_key)

        # Use AWS hooks for connection
        hook = AwsBaseHook(aws_conn_id=self.aws_conn_id)
        session = hook.get_session()

        try:
            # Perform operation
            result = self.perform_operation()
            return result
        except Exception as e:
            logger.error(f"Operation failed: {str(e)}")
            raise AirflowException(f"Custom operator failed: {str(e)}")
```

#### XCom Data Flow

```python
# Push data to XCom
task_instance.xcom_push(key='extraction_metadata', value=extraction_data)

# Pull data from XCom
extraction_data = task_instance.xcom_pull(
    task_ids='previous_task',
    key='extraction_metadata'
)

# Pull entire XCom
response = task_instance.xcom_pull(task_ids='lambda_task')
```

#### DAG Definition

```python
from airflow import DAG
from datetime import datetime, timedelta

dag = DAG(
    'catalunya_social_services_pipeline',
    default_args={
        'owner': 'catalunya-data-team',
        'depends_on_past': False,
        'start_date': datetime(2024, 1, 1),
        'email_on_failure': True,
        'retries': 2,
        'retry_delay': timedelta(minutes=5),
        'execution_timeout': timedelta(minutes=15),
    },
    description=f'Catalunya Social Services Pipeline - {ENVIRONMENT}',
    schedule='0 23 * *',  # Cron expression
    catchup=False,
    max_active_runs=1,
    tags=['catalunya', 'social-services', f'env:{ENVIRONMENT}'],
)

# Environment-specific configuration
ENV_CONFIG = {
    "dev": {
        "aws_conn_id": "aws_cross_account_role",
        "schedule": "0 23 * *",
        "timeout_minutes": 15,
    },
    "prod": {
        "aws_conn_id": "aws_cross_account_role",
        "schedule": "0 23 * *",
        "timeout_minutes": 20,
    },
}

config = ENV_CONFIG.get(ENVIRONMENT)
```

#### Task Dependencies

```python
# Linear chain
task1 >> task2 >> task3 >> task4

# Branching
task1 >> [task2a, task2b] >> task3

# Multiple upstreams
[task1, task2] >> task3

# With Jinja templates
prepare_payload_task >> invoke_lambda >> parse_response >> next_task
```

---

## Testing Guidelines

### Python Unit Tests

```python
import unittest
from unittest.mock import patch, MagicMock

class TestSocialServicesApiExtractor(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "BUCKET_NAME": "test-bucket",
            "DATASET_IDENTIFIER": "test-dataset",
        },
    )
    @patch("api_extractor.get_s3_client")
    def test_lambda_handler_success(self, mock_s3_client, mock_urlopen):
        """Test successful lambda execution"""
        # Setup mocks
        mock_s3 = MagicMock()
        mock_s3_client.return_value = mock_s3

        # Execute
        result = lambda_handler({}, None)

        # Assertions
        self.assertEqual(result["statusCode"], 200)
        self.assertTrue(result["success"])
        self.assertIn("data", result)

if __name__ == "__main__":
    unittest.main()

# Run single test
python -m unittest test_api_extractor TestSocialServicesApiExtractor.test_lambda_handler_success
```

### Rust Unit Tests

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_function_success() {
        let input = LambdaInput {
            source_prefix: "test/prefix".to_string(),
        };

        let result = function_handler(input);

        assert!(result.is_ok());
        let output = result.unwrap();
        assert_eq!(output.status, "succeeded");
    }

    #[test]
    fn test_error_handling() {
        let result = process_data("");
        assert!(result.is_err());
    }
}

// Run tests
cargo test

// Run single test
cargo test test_function_success
```

### TypeScript/CDK Tests

```typescript
import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { CatalunyaDataStack } from '../lib/infrastructure-stack';

describe('Catalunya Data Stack', () => {
    let app: cdk.App;

    beforeEach(() => {
        app = new cdk.App({
            context: {
                'Catalunya-Data-Pipeline': {
                    'dev': { /* config */ },
                }
            }
        });
    });

    test('Development stack synthesizes correctly', () => {
        const stack = new CatalunyaDataStack(app, 'TestDevStack', {
            environmentName: 'dev',
            projectName: 'test-catalunya-dev',
        });

        const template = Template.fromStack(stack);

        // Verify outputs exist
        expect(template.toJSON().Outputs).toBeDefined();
        expect(Object.keys(template.toJSON().Outputs || {}).length).toBeGreaterThan(0);
    });

    test('Invalid environment throws error', () => {
        expect(() => {
            new CatalunyaDataStack(app, 'TestInvalidStack', {
                environmentName: 'invalid',
            });
        }).toThrow('Invalid environment: invalid');
    });
});
```

---

## Common Patterns

### Environment Variables

**Python Lambda**:
- `BUCKET_NAME`: S3 bucket for data operations
- `CATALOG_BUCKET_NAME`: S3 bucket for catalog data
- `DATASET_IDENTIFIER`: Dataset ID for API calls
- `SEMANTIC_IDENTIFIER`: Semantic identifier for S3 paths
- `ENVIRONMENT`: Environment name (local/dev/prod)
- `AWS_ENDPOINT_URL`: Optional LocalStack endpoint

**Rust Lambda**:
- `BUCKET_NAME`: S3 bucket for data operations
- `CATALOG_BUCKET_NAME`: S3 bucket for catalog data
- `SEMANTIC_IDENTIFIER`: Semantic identifier for S3 paths
- `ENVIRONMENT`: Environment name (local/dev/prod)
- `REGION`: AWS region (default: eu-west-1)
- `ATHENA_DATABASE_NAME`: Athena database name

**dbt**:
- `DATA_BUCKET`: S3 bucket name via `env_var('DATA_BUCKET')`
- `CATALOG_BUCKET`: Catalog bucket via `env_var('CATALOG_BUCKET')`

### S3 Key Conventions

```
landing/{semantic_identifier}/downloaded_date={YYYYMMDD}/{offset:08d}.json
staging/{semantic_identifier}/downloaded_date={YYYYMMDD}/{semantic_identifier}.parquet
marts/{semantic_identifier}/{semantic_identifier}.parquet
catalog/{catalog_name}/{catalog_name}.parquet
```

### Lambda Response Format

```python
# Standard response structure
def create_response(
    success: bool,
    message: str,
    data: Optional[Dict[str, Any]] = None,
    error_type: Optional[str] = None,
) -> Dict[str, Any]:
    response: Dict[str, Any] = {
        "statusCode": 200 if success else 500,
        "success": success,
        "message": message,
        "timestamp": get_current_time().isoformat(),
        "processor": "function-name",
    }

    if data:
        response["data"] = data

    if error_type:
        if "data" not in response:
            response["data"] = {}
        response["data"]["error_type"] = error_type

    return response
```

### Cross-Account IAM

Airflow assumes roles in target AWS account using external ID:

```python
# Airflow connection stores access key/secret for assumer user
# Assumer user has minimal permissions: only AssumeRole

# Role ARN pattern
role_arn = f"arn:aws:iam::{account_id}:role/catalunya-s3-copier-{role_type}-role-{ENVIRONMENT}"

# External ID for security
external_id = f"catalunya-{environment}-airflow-exec"
```

---

## Project Structure

```
CloudGentGran/
├── infrastructure/              # AWS CDK TypeScript
│   ├── lib/                    # Constructs
│   ├── test/                   # CDK tests
│   └── cdk.json                # Configuration
├── lambda/                    # Lambda functions
│   ├── common/                  # Shared Python code
│   ├── extractors/              # Python API extractors
│   ├── catalog/                 # Python catalog initializers
│   ├── transformers/             # Rust transformers
│   └── mart/                    # Rust marts
├── dbt/mart/                  # dbt models
│   ├── models/                  # SQL models
│   ├── macros/                  # Jinja macros
│   └── dbt_project.yml        # dbt config
├── orchestration/              # Airflow DAGs
│   ├── dags/                    # DAG definitions
│   └── plugins/                  # Custom operators
└── observable/                 # Observable Framework dashboards
    └── projects/gent-gran/      # Project code
```

---

## Quick Reference

### Run Single Test

```bash
# Python
python -m unittest path/to/test.py TestClass.test_method

# Rust
cargo test test_name

# TypeScript
npm test -- --testNamePattern="test_name"
```

### Build Specific Component

```bash
# Infrastructure
cd infrastructure && npm run build

# Python lambda (no build step, just deploy via CDK)

# Rust lambda
cd lambda/transformers/social_services && cargo lambda build --release

# dbt
cd dbt/mart && dbt run --select specific_model
```

### Debug Tips

- **Python**: Add `import pdb; pdb.set_trace()` at breakpoint, use `python -m pdb test_xxx.py`
- **Rust**: Use `dbg!(&variable)` macro for debugging
- **Airflow**: Check logs at `Admin → Browse → Task Instances → Logs`
- **Lambda**: Check CloudWatch logs via AWS Console or CLI: `aws logs tail /aws/lambda/function-name --follow`
- **CDK**: Use `npx cdk synth` to view generated CloudFormation template
