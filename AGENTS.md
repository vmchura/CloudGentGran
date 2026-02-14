# AGENTS.md - Catalunya Data Pipeline Development Guide

Coding guidelines and conventions for AI coding agents in this repository.

---

## Build/Test Commands

### Infrastructure (CDK/TypeScript)
```bash
cd infrastructure
npm run build          # Build TypeScript
npm test               # Run all tests
npm test -- --testNamePattern="test_name"  # Run single test
npx cdk synth          # Synthesize CloudFormation template
npx cdk deploy CatalunyaDataStack-dev      # Deploy to dev
```

### Python Lambda Functions
```bash
cd lambda/extractors/<function_name>
pip install -r requirements.txt
python -m unittest test_<name>.py                           # All tests
python -m unittest test_<name>.py TestClass.test_method     # Single test
AWS_ENDPOINT_URL=http://localhost:4566 python -m lambda lambda_function  # LocalStack
```

### Rust Lambda Functions
```bash
cd lambda/transformers/<function_name>/
cargo lambda build --release --target x86_64-unknown-linux-gnu  # Production build
cargo test                    # All tests
cargo test test_name          # Single test
cargo fmt                     # Format code
cargo clippy                  # Lint
```

### dbt Models
```bash
cd dbt/mart
dbt run --select model_name   # Run specific model
dbt test                      # Run all tests
DATA_BUCKET=catalunya-data-dev dbt run --target dev
```

### Airflow DAGs
```bash
cd orchestration
python -m py_compile dags/<dag_file>.py    # Test DAG syntax
airflow dags trigger <dag_name>
```

---

## Code Style Guidelines

### Python (Extractors, Orchestration)

**Imports Order**: Standard library → Third-party → Local modules
```python
import json
from typing import Dict, Any, Optional
import boto3
from common.exceptions import LambdaError, ConfigurationError, APIError
```

**Type Annotations**: Required for all function signatures
```python
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
def upload_to_s3(bucket_name: str, data: bytes, key: str) -> str:
```

**Naming Conventions**:
- Files: `snake_case.py` (e.g., `api_extractor.py`)
- Classes: `PascalCase` (e.g., `S3CopyWithRoleOperator`)
- Functions: `snake_case` (e.g., `lambda_handler`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRIES`)

**Error Handling**: Use custom exceptions from `lambda/common/exceptions.py`:
```python
from common.exceptions import ConfigurationError, APIError, S3OperationError
raise ConfigurationError(f"Missing env vars: {', '.join(missing_vars)}")
```

**Logging**: Use `logger = logging.getLogger(__name__)` with info/warning/error levels.

---

### Rust (Transformers, Marts)

**Naming Conventions**:
- Files/Modules: `snake_case` (e.g., `generic_handler.rs`)
- Structs: `PascalCase` (e.g., `LambdaInput`, `ProcessingResult`)
- Functions: `snake_case` (e.g., `function_handler`, `upload_to_s3`)
- Constants: `SCREAMING_SNAKE_CASE` (e.g., `MAX_RETRIES`)

**Error Handling**: Use `anyhow::Result<T>`:
```rust
use anyhow::{anyhow, Result};
fn process_data(input: &str) -> Result<DataFrame> {
    if input.is_empty() {
        return Err(anyhow!("Input is empty"));
    }
    Ok(dataframe)
}
```

**Entry Point**: Lambda functions use `lambda_runtime` with `#[tokio::main]`.

**Workspace Dependencies**: All Rust lambdas use workspace dependencies from `lambda/Cargo.toml`.

---

### TypeScript (CDK Infrastructure)

**Type Safety**: Strict mode enabled (`strict: true`, `noImplicitAny: true`, `strictNullChecks: true`)

**Naming Conventions**:
- Interfaces: `PascalCase` ending in `Props` (e.g., `LambdaConstructProps`)
- Classes: `PascalCase` ending in `Construct` (e.g., `LambdaConstruct`)
- Methods/Properties: `camelCase`

**Resource Naming**:
- Lambda: `{lambdaPrefix}-{function_name}`
- IAM roles: `catalunya-{layer}-role-{environment}`
- S3 buckets: `catalunya-{type}-{environmentName}`

---

### SQL (dbt Models)

**Formatting**: Uppercase keywords, lowercase column names, 2-space indentation

**Use CTEs** for complex queries. Use project macros:
```sql
{{ adapter_aware_table_config() }}
FROM {{ read_staging_data('social_services', 'downloaded_date', var('downloaded_date')) }}
JOIN {{ read_catalog_data('municipals') }} m ON data.municipal_id = m.municipal_id
```

---

### Airflow DAGs and Operators

**Operator Pattern**: Extend `BaseOperator`, use `template_fields` for Jinja support, type annotations required.

**DAG Definition**: Include owner, retries, timeout, tags. Use environment-specific configs.

**Task Dependencies**: Use `>>` operator (e.g., `task1 >> task2 >> task3`)

**XCom**: Use `xcom_push`/`xcom_pull` for inter-task data flow.

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

- **Python**: `import pdb; pdb.set_trace()` or `python -m pdb test_xxx.py`
- **Rust**: `dbg!(&variable)` macro
- **Airflow**: Admin → Browse → Task Instances → Logs
- **Lambda**: `aws logs tail /aws/lambda/function-name --follow`
- **CDK**: `npx cdk synth` to view CloudFormation template
