# System Architecture

## Overview

The Catalunya Open Data Pipeline is designed as a multi-environment data platform that extracts, transforms, and loads (ETL) open data from Catalunya government sources using Apache Airflow orchestration across three distinct environments. The pipeline processes data through multiple layers, culminating in a public-facing data service powered by Observable Framework.

## Environment Architecture

### Local Environment
- **Purpose**: Isolated development of individual modules with full mocking
- **Storage**: Local folders, DuckDB database
- **Orchestration**: Apache Airflow (Docker Compose)  
- **Processing**: Mocked services for rapid development
- **Data Sources**: Mock APIs and sample data files

### Development Environment
- **Purpose**: Production-like testing with full AWS integration
- **Storage**: AWS S3, AWS Athena with Glue Data Catalog
- **Orchestration**: Apache Airflow (Dokku on-premise server)
- **Processing**: Full AWS Lambda integration
- **Data Sources**: Real Catalunya APIs with development configurations

### Production Environment  
- **Purpose**: Production workloads with high availability
- **Storage**: AWS S3, AWS Athena with Glue Data Catalog
- **Orchestration**: Apache Airflow (Dokku on-premise server)
- **Processing**: Full AWS Lambda integration  
- **Data Sources**: Real Catalunya APIs with production configurations

### 1. Landing Layer (`s3://data-bucket/landing/`)

**Purpose**: Store raw, unprocessed data exactly as received from source APIs.

**Characteristics**:

- **Format**: JSON files
- **Partitioning**: `source/partition=partition_value/partitions_.json`
- **Retention**: ephemeral, deleted once further staging dependency fulfills data quality.
- **Processing**: No transformations, direct API response storage

**Example Structure**:

```
s3://catalunya-data-dev/landing/
├── social_services/downloaded_date=20250914/files.json
└── social_services/downloaded_date=20250915/files.json
```

### 2. Staging Layer (`s3://data-bucket/staging/`)

**Purpose**: Store cleaned, validated, and standardized data ready for analytics.

**Characteristics**:

- **Format**: Parquet (columnar, compressed)
- **Partitioning**: `source/functional_partition=partition_vale`
- **Retention**: 3 months
- **Processing**: Data cleaning, validation, type casting, deduplication

**Schema Enforcement**:

- Consistent column
  names [dbt Labs suggestions](https://docs.getdbt.com/best-practices/how-we-style/1-how-we-style-our-dbt-models)
- Standardized data types
- Required field validation
- Data quality checks

**Example Structure**:

```
s3://catalunya-data-dev/staging/
├── social_services/district_id=01/file.parquet
└── social_services/district_id=02/file.parquet
```

### 3. Marts Layer (`s3://data-bucket/marts/`)

**Purpose**: Business-ready dimensional models optimized for analytics and reporting.

**Characteristics**:

- **Format**: Parquet (optimized for queries)
- **Partitioning**: Optimized for common query patterns
- **Retention**: 3 months
- **Processing**: Dimensional modeling, aggregations, business logic

**Model Types**:

- **Fact Tables**: Metrics and measurements over time
- **Aggregate Tables**: Pre-computed summaries for performance

**Example Structure**:

```
s3://catalunya-data-dev/marts/
└── social_services_by_service_municipal/
    └── file.parquet
```

### 4. Service Layer (`s3://data-bucket/dataservice/`)

**Purpose**: Public-ready datasets optimized for external consumption via Observable Framework.

**Characteristics**:

- **Format**: Observable target build directory
- **Retention**: 60 days
- **Processing**: Final formatting for visualization and API consumption

### 5. Catalog Layer (`s3://catalog-bucket/`)

**Purpose**: Metadata, schemas, and data dictionary for pipeline operations.

**Characteristics**:

- **Format**: JSON schemas, Avro schemas, documentation
- **Access**: Read-only for transformation processes
- **Retention**: Permanent with versioning
- **Content**: Schema definitions, field mappings, business rules

**Catalog Types**:

- **Schema Registry**: Versioned data schemas
- **Transformation Rules**: Business logic definitions
- **Data Dictionary**: Field descriptions and metadata

## Technology Stack Details

### Apache Airflow

**Local Environment**:
- **Runtime**: Docker Compose with LocalExecutor
- **Database**: PostgreSQL (containerized)
- **Configuration**: Single container with webserver/scheduler

**Development/Production Environments**:
- **Runtime**: Dokku deployment on on-premise servers
- **Database**: PostgreSQL (managed or containerized)
- **Configuration**: Multi-process setup with separate workers

### Data Processing

**Local Environment**:
- **Database**: DuckDB for development and testing
- **Storage**: Local filesystem and Docker volumes
- **Processing**: Python scripts with mocked external services

**Development/Production Environments**:
- **AWS Lambda**: Python 3.12 runtime for data extraction/transformation
- **Amazon S3**: Multi-tier storage (Landing, Staging, Marts, Service, Catalog)
- **Amazon Athena**: SQL query engine with Glue Data Catalog
- **S3 Copiers**: Direct layer-to-layer data transfer roles

### DBT Core

**Purpose**: SQL-based transformations and data modeling

**Features**:
- **Incremental Models**: Process only new/changed data
- **Testing**: Automated data quality tests
- **Documentation**: Auto-generated data catalog
- **Lineage**: Track data dependencies

**Adapters**:
- **Local**: DuckDB adapter
- **Development/Production**: Athena adapter

### Observable Framework

**Purpose**: Public data visualization and dashboard platform

**Features**:
- **Interactive Dashboards**: Real-time data visualization
- **Public Access**: No authentication required
- **Data Loaders**: Direct S3 integration via CloudFront
- **Responsive Design**: Mobile and desktop optimized

**Architecture**:
- **Static Site Generation**: Build-time data processing
- **CDN Distribution**: CloudFront for global performance
- **Data Source**: Service layer S3 bucket
- **Update Frequency**: Daily refreshes via CI/CD

### Infrastructure

**Local Environment**:
- **Orchestration**: Docker Compose
- **Configuration**: Environment variables and local files

**Development/Production Environments**:
- **Infrastructure as Code**: AWS CDK (TypeScript)
- **Deployment**: Dokku for Airflow, CDK for AWS resources
- **Monitoring**: CloudWatch and Airflow native monitoring

## Security Architecture

### Local Environment
- **Access Control**: Local Docker containers, no external access required
- **Data Security**: Local filesystem permissions, development data only
- **Network**: Isolated Docker network, localhost access only

### Development/Production Environments

### Access Control

**Principle of Least Privilege**:
- Lambda functions have minimal required permissions
- Cross-account access through assumed roles
- Resource-based policies for S3 buckets

**IAM Structure**:

#### **Catalunya Data Engineer Role** (`catalunya-data-engineer-role`)
**Purpose**: Primary development and management role for the data pipeline project.

**Intended Users**: Project maintainers and core developers who need comprehensive access to develop, deploy, and manage the Catalunya data pipeline infrastructure.

**Access Pattern**: Assumed by IAM users with MFA authentication required for security compliance.

#### **Service Account Roles**

**Lambda Extractor Roles**
- `catalunya-lambda-extractor-role-dev`
- `catalunya-lambda-extractor-role-prod`

**Purpose**: Execute data extraction operations from Catalunya government APIs to the landing layer.

**Runtime Context**: AWS Lambda functions triggered by Apache Airflow on defined intervals (daily/weekly).

**Data Flow Position**: External APIs → Lambda Extractor → S3 Landing Layer

**Security Boundaries**: 
- Can only write to S3 landing layer (`s3://catalunya-data-{env}/landing/*`)
- Internet access for external API calls

**Lambda Transformer Roles**
- `catalunya-lambda-transformer-role-dev`
- `catalunya-lambda-transformer-role-prod`

**Purpose**: Process and clean raw data from landing layer into validated, analytics-ready format in staging layer.

**Runtime Context**: AWS Lambda functions triggered by Apache Airflow workflows.

**Data Flow Position**: S3 Landing Layer → Lambda Transformer → S3 Staging Layer

**Security Boundaries**:
- Read access to S3 landing layer and catalog bucket
- Write access to S3 staging layer only

**S3 Copier Roles**
- `catalunya-s3-copier-transformer-role-dev`
- `catalunya-s3-copier-transformer-role-prod`
- `catalunya-s3-copier-mart-role-dev`
- `catalunya-s3-copier-mart-role-prod`

**Purpose**: Direct transfer of data between S3 layers without processing.

**Runtime Context**: AWS Lambda functions for efficient bulk transfers.

**Data Flow Position**: 
- Transformer: Landing → Staging or Staging → Marts
- Mart: Marts → Service

**Security Boundaries**:
- Source layer read-only access
- Target layer write-only access
- No data transformation capabilities

**Data Service Role**
- `catalunya-data-service-role-dev`
- `catalunya-data-service-role-prod`

**Purpose**: Prepare and publish data for public consumption via Observable.

**Runtime Context**: Lambda functions managing public data exposure.

**Data Flow Position**: S3 Marts → S3 Service Layer

**Security Boundaries**:
- Read access to marts layer
- Write access to service bucket only
- CloudFront distribution management

**GitHub Actions Deployment Roles**
- `catalunya-deployment-role-dev` (OIDC: develop branch)
- `catalunya-deployment-role-prod` (OIDC: main branch)

**Purpose**: Deploy infrastructure and application updates through CI/CD pipelines.

**Runtime Context**: GitHub Actions workflows triggered by code pushes to specific branches.

**Security Boundaries**:
- OIDC authentication tied to specific Git branches (develop/main)
- CloudFormation deployment permissions
- Environment-specific resource access

**Mart Processing Roles**
- `catalunya-mart-role-dev`
- `catalunya-mart-role-prod`

**Purpose**: Execute DBT transformations to create business-ready analytics models from staging data.

**Runtime Context**: Apache Airflow DAGs executing DBT Core commands.

**Data Flow Position**: S3 Staging Layer → DBT/Athena → S3 Marts Layer

**Security Boundaries**:
- Read access to S3 staging layer and Glue Data Catalog
- Write access to S3 marts layer
- Athena query execution permissions within designated workgroup
- Access to dedicated Athena results S3 bucket

**Monitoring Roles**
- `catalunya-monitoring-role-dev`
- `catalunya-monitoring-role-prod`

**Purpose**: Operational observability, alerting, and cost optimization across the data pipeline.

**Runtime Context**: Monitoring services and alerting systems.

**Security Boundaries**:
- Read-only access to all data layers for monitoring purposes
- CloudWatch and SNS permissions for alerting
- Cost Explorer access for usage analysis

### Network Security

**Local Environment**:
- Docker network isolation
- No external network access required

**Development/Production Environments**:
- Lambda functions with internet access for API calls
- Dokku server network configuration for Airflow

## Monitoring & Observability

### Local Environment

**Monitoring Tools**:
- Airflow Web UI at http://localhost:8080
- Local log files in orchestration/logs/
- DuckDB database inspection and query tools
- Docker container logs via `docker-compose logs`

**Metrics Available**:
- DAG execution status and duration
- Local data processing metrics
- Container resource usage

### Development/Production Environments

**Airflow Monitoring**:
- Airflow Web UI on Dokku servers
- DAG execution logs and metrics
- Task failure notifications
- Scheduler and worker health monitoring

**AWS Infrastructure Monitoring**:
- CloudWatch Logs for Lambda functions
- Custom CloudWatch metrics for data pipeline health
- SNS notifications for pipeline failures
- CloudWatch Dashboard for operational overview

**Data Quality Monitoring**:
- DBT test results and data lineage

### Logging Strategy

**Log Levels**:
- **ERROR**: Pipeline failures, data quality issues
- **WARN**: API timeouts, retry attempts  
- **INFO**: Successful processing, row counts
- **DEBUG**: Detailed processing steps (local/dev only)

**Log Aggregation**:
- Local: File-based logging
- Development/Production: CloudWatch Log Groups + Airflow logs
- Structured JSON logging with correlation IDs

### Dashboards

**Local Environment**:
- Airflow UI for pipeline monitoring
- Local development metrics

**Development/Production Environments**:
- Operational Dashboard: Pipeline health, processing times, error rates
- Cost Dashboard: Resource usage and cost tracking

## Scalability Considerations

### Local Environment

**Resource Management**:
- Docker container resource limits
- DuckDB performance tuning for development datasets
- Local storage management and cleanup

### Development/Production Environments

**Airflow Scaling**:
- Dokku process scaling for worker nodes
- Task parallelization and resource allocation
- Queue management for task distribution

**AWS Lambda Scaling**:
- Concurrency management for consistent performance
- Dead letter queues for failed executions
- Retry logic with exponential backoff

**Storage Performance**:
- S3 request patterns with random prefixes
- Multipart upload for large files
- Transfer acceleration for global access

**Query Engine Optimization**:
- Athena query performance with partitioning
- Columnar format (Parquet) for analytical workloads
- Compression to reduce scan costs
- DuckDB optimization for local development

## Cost Optimization

### Local Environment
- **Infrastructure Cost**: $0 (runs entirely on local machine)
- **Resource Usage**: Minimal Docker container overhead
- **Development Speed**: Fast iteration without cloud costs

### Production/Development Environment
| Service         | Usage                  | Estimated Cost         |
|-----------------|------------------------|------------------------|
| S3 Storage      | 10GB across all layers | < $0.25/month          |
| Lambda Requests | 5K invocations/month   | < $1.00/month          |
| Athena Queries  | 50GB scanned/month     | < $1.00/month          |
| CloudWatch      | Logs + Metrics         | < $1.00/month          |
| Dokku Server    | On-premise hosting     | Variable               |
| **Total**       |                        | **< ~$3.25 + hosting** |

