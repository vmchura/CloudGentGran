# AGENTS.md - Catalunya Data Pipeline Development Guide

Coding guidelines and conventions for AI coding agents in this repository.

## Build/Test Commands

### Infrastructure (CDK/TypeScript)
```bash
cd infrastructure
npm run build                    # Compile TypeScript
npm test                         # All tests
npm test -- --testNamePattern="test_name"  # Single test
npx cdk synth && npx cdk deploy CatalunyaDataStack-dev
```

### Python Lambda Functions
```bash
cd lambda/extractors/<function_name>
pip install -r requirements.txt
python -m unittest test_<name>.py                 # All tests
python -m unittest test_<name>.py TestClass.test_method  # Single test
AWS_ENDPOINT_URL=http://localhost:4566 python -m lambda lambda_function
```

### Rust Lambda Functions
```bash
cd lambda/transformers/<function_name>/
cargo lambda build --release --target x86_64-unknown-linux-gnu
cargo test                        # All tests
cargo test test_name              # Single test
cargo fmt --check && cargo clippy
```

### dbt, Airflow & Observable
```bash
cd dbt/mart && dbt run --select model_name   # Run specific dbt model
cd orchestration && python -m py_compile dags/<dag_file>.py  # DAG syntax
cd observable && npm run dev      # Observable local server
```

---

## Code Style Guidelines

### Python (Extractors, Orchestration)

**Imports**: Standard library → Third-party → Local modules
```python
import json
from typing import Dict, Any, Optional
import boto3
from airflow.sdk import BaseOperator
from common.exceptions import ConfigurationError, APIError
```

**Type Annotations**: Required for all function signatures
```python
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
def upload_to_s3(bucket_name: str, data: bytes, key: str) -> str:
```

**Naming**: Files `snake_case.py`, Classes `PascalCase`, Functions `snake_case`, Constants `UPPER_SNAKE_CASE`

**Error Handling**: Use custom exceptions from `lambda/common/exceptions.py`:
```python
from common.exceptions import ConfigurationError, APIError, S3OperationError
raise ConfigurationError(f"Missing env vars: {', '.join(missing_vars)}")
```

**Logging**: Use `logger = logging.getLogger(__name__)` with info/warning/error levels.

### Rust (Transformers, Marts)

**Naming**: Files `snake_case.rs`, Structs `PascalCase`, Functions `snake_case`, Constants `SCREAMING_SNAKE_CASE`

**Error Handling**: Use `anyhow::Result<T>`:
```rust
use anyhow::{anyhow, Result};
fn process_data(input: &str) -> Result<DataFrame> {
    if input.is_empty() { return Err(anyhow!("Input is empty")); }
    Ok(dataframe)
}
```

**Entry Point**: Lambda functions use `lambda_runtime` with `#[tokio::main]`. Workspace dependencies from `lambda/Cargo.toml`.

### TypeScript (CDK Infrastructure)

**Type Safety**: Strict mode (`strict: true`, `noImplicitAny: true`, `strictNullChecks: true`)

**Naming**: Interfaces `PascalCaseProps` (e.g., `LambdaConstructProps`), Classes `PascalCaseConstruct`, Methods `camelCase`

**Resource Naming**: Lambda `{prefix}-{function}`, IAM roles `catalunya-{layer}-role-{env}`, S3 buckets `catalunya-{type}-{env}`

### SQL (dbt Models)

**Formatting**: Uppercase keywords, lowercase columns, 2-space indentation. Use CTEs for complex queries.

**Macros**:
```sql
{{ adapter_aware_table_config() }}
FROM {{ read_staging_data('social_services', 'downloaded_date', var('downloaded_date')) }}
JOIN {{ read_catalog_data('municipals') }} m ON data.municipal_id = m.municipal_id
```

### Airflow DAGs and Operators

Extend `BaseOperator`, use `template_fields` for Jinja support, type annotations required. DAGs should include owner, retries, timeout, tags. Use `Variable.get()` for environment configs. Task dependencies via `>>` operator. Use `xcom_push`/`xcom_pull` for inter-task data flow.

---

## Environment Variables

**Python Lambda**: `BUCKET_NAME`, `CATALOG_BUCKET_NAME`, `DATASET_IDENTIFIER`, `SEMANTIC_IDENTIFIER`, `ENVIRONMENT`, `AWS_ENDPOINT_URL`

**Rust Lambda**: `BUCKET_NAME`, `CATALOG_BUCKET_NAME`, `SEMANTIC_IDENTIFIER`, `ENVIRONMENT`, `REGION`, `ATHENA_DATABASE_NAME`

**dbt**: `DATA_BUCKET`, `CATALOG_BUCKET` via `env_var()`

---

## S3 Key Conventions

```
landing/{semantic_identifier}/downloaded_date={YYYYMMDD}/{offset:08d}.json
staging/{semantic_identifier}/downloaded_date={YYYYMMDD}/{semantic_identifier}.parquet
marts/{semantic_identifier}/{semantic_identifier}.parquet
catalog/{catalog_name}/{catalog_name}.parquet
```

---

## Project Structure

```
CloudGentGran/
├── infrastructure/        # AWS CDK TypeScript
├── lambda/
│   ├── common/            # Shared Python code (exceptions.py)
│   ├── extractors/        # Python API extractors
│   ├── catalog/           # Python catalog initializers
│   ├── transformers/      # Rust transformers
│   └── mart/              # Rust marts
├── dbt/mart/              # dbt models and macros
├── orchestration/         # Airflow DAGs and plugins
└── observable/            # Observable Framework dashboards
```

---

## Debug Tips

- **Python**: `import pdb; pdb.set_trace()`
- **Rust**: `dbg!(&variable)` macro
- **Airflow**: Admin → Browse → Task Instances → Logs
- **Lambda**: `aws logs tail /aws/lambda/function-name --follow`
- **CDK**: `npx cdk synth` to view CloudFormation template
