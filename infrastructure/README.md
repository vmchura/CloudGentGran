# Catalunya Data Pipeline Infrastructure

This directory contains the AWS CDK TypeScript infrastructure code for the Catalunya Open Data Pipeline project.

## 📁 Project Structure

```
infrastructure/
├── bin/
│   └── infrastructure.ts      # CDK app entry point with dev/prod stacks
├── lib/
│   ├── infrastructure-stack.ts # Main Catalunya Data Stack
│   ├── config.ts              # Configuration helper utilities
│   ├── iam-construct.ts       # IAM roles and policies
│   ├── s3-construct.ts        # S3 buckets with lifecycle policies
│   ├── lambda-construct.ts    # Lambda functions and triggers
│   ├── analytics-construct.ts # Athena workgroups and databases
│   ├── catalog-construct.ts   # Data catalog functions
│   ├── glue-construct.ts      # Glue jobs and crawlers
│   └── web-construct.ts       # CloudFront and Route53 (optional)
├── test/
│   └── infrastructure.test.ts # Unit tests for the stack
├── cdk.json                   # CDK configuration and context
├── package.json               # Dependencies and scripts
└── tsconfig.json             # TypeScript configuration
```

## 🏗️ Architecture Overview

The infrastructure follows a **multi-environment architecture** with separate dev and prod stacks:

- **Environment Isolation**: Complete separation between dev and prod environments
- **Configuration-Driven**: Environment-specific settings managed via `cdk.json`
- **Scalable Naming**: Consistent resource naming with environment prefixes
- **Export Values**: Stack outputs are exported for cross-stack references

## 🚀 Getting Started

### Prerequisites

- Node.js 18+ installed
- AWS CLI configured with appropriate credentials
- AWS CDK CLI installed globally: `npm install -g aws-cdk`

### Installation

```bash
cd infrastructure
npm install
```

### Build and Test

```bash
# Build TypeScript
npm run build

# Run unit tests
npm test

# List all stacks
npx cdk list

# Synthesize a specific stack
npx cdk synth CatalunyaDataStack-dev
```

## 🔧 Configuration

Environment-specific configuration is managed in `cdk.json` under the `Catalunya-Data-Pipeline` context:

```json
{
  "context": {
    "Catalunya-Data-Pipeline": {
      "dev": {
        "...": ""
      },
      "prod": {
        "...": ""
      }
    }
  }
}
```

### Configuration Parameters

| Parameter         | Description                           | Dev Value            | Prod Value            |
|-------------------|---------------------------------------|----------------------|-----------------------|
| `region`          | AWS region for deployment             | `eu-west-1`          | `eu-west-1`           |
| `bucketName`      | S3 bucket name                        | `catalunya-data-dev` | `catalunya-data-prod` |
| `catalogBucketName` | Catalog data bucket name            | `catalunya-catalog-dev` | `catalunya-catalog-prod` |
| `serviceBucketName` | Service/static assets bucket name   | `catalunya-service-dev` | `catalunya-service-prod` |
| `lambdaMemory`    | Lambda memory allocation (MB)         | `512`                | `1024`                |
| `lambdaTimeout`   | Lambda timeout (seconds)              | `300`                | `900`                 |
| `retentionPeriod` | Data retention period (days)[landing] | `7` or `ephemeral`   | `7` or `ephemeral`    |
| `retentionPeriod` | Data retention period (days)[staging] | `60`                 | `60`                  |
| `retentionPeriod` | Data retention period (days)[marts]   | `60`                 | `60`                  |
| `webDomain`       | Web domain (optional)                 | `gentgran.cat`       | `gentgran.cat`        |
| `webSubdomain`    | Web subdomain (optional)              | `observatori`        | `observatori`         |

## 📦 Stack Resources

The `CatalunyaDataStack` creates the following resources:

### Implemented Resources

- **S3 Buckets**: Data storage with medallion architecture (landing/staging/marts)
  - Landing bucket: 7-day retention
  - Staging/Marts: 60-day IA transition after 60 days
  - Athena results bucket for query outputs
- **Lambda Functions**: Rust-based data extraction and transformation
  - Social services transformer
  - Population municipal processors
  - Mart generators
- **IAM Roles**: Service-specific permissions with least privilege
  - Extractor, Transformer, Mart, Monitoring roles
  - Data engineer human access role
  - Airflow cross-account execution role
- **Athena Infrastructure**: Query processing and cost controls
  - Workgroups with result configuration
  - Database for data catalog
- **Glue Infrastructure**: Table schema management
  - Crawlers for data discovery
  - Database catalog integration
- **Web Infrastructure** (Optional): CloudFront + Route53
  - Requires WEB_CERTIFICATE_ID environment variable
- **CloudFormation Outputs**: Complete resource reference exports
- **Tags**: Automatic tagging with project, environment, owner, and management info

## 🌍 Environments

### Development (`dev`)

- **Stack Name**: `CatalunyaDataStack-dev`
- **Resource Prefix**: `catalunya-dev`
- **Purpose**: Testing and development
- **Scaling**: Minimal resources, shorter retention

### Production (`prod`)

- **Stack Name**: `CatalunyaDataStack-prod`
- **Resource Prefix**: `catalunya-prod`
- **Purpose**: Live data processing
- **Scaling**: Enhanced resources, longer retention

## 🔄 Deployment Commands

```bash
# Bootstrap CDK (one-time setup)
npx cdk bootstrap

# Deploy development environment
npx cdk deploy CatalunyaDataStack-dev

# Deploy production environment
npx cdk deploy CatalunyaDataStack-prod

# Deploy all stacks
npx cdk deploy --all

# Destroy development environment (careful!)
npx cdk destroy CatalunyaDataStack-dev
```

## 🧪 Testing

The project includes comprehensive unit tests:

```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test -- --watch

# Run tests with coverage
npm run test -- --coverage
```

### Test Coverage

- ✅ Stack synthesis validation
- ✅ Environment-specific configuration
- ✅ Output validation
- ✅ Error handling for invalid environments

## 📊 Stack Outputs

Each stack exports the following values for use by other stacks:

| Output                       | Description                              | Export Name Format                      |
|------------------------------|------------------------------------------|-----------------------------------------|
| `Environment`                | Environment name (dev/prod)              | `{projectName}-Environment`            |
| `BucketName`                 | Main S3 bucket name                      | `{projectName}-BucketName`             |
| `AthenaResultsBucketName`    | Athena query results bucket              | `{projectName}-AthenaResultsBucket`    |
| `AthenaWorkgroup`            | Athena workgroup name                   | `{projectName}-AthenaWorkgroup`        |
| `AthenaDatabase`             | Athena database name                    | `{projectName}-AthenaDatabase`         |
| `LambdaPrefix`               | Lambda function prefix                  | `{projectName}-LambdaPrefix`           |
| `Region`                     | Deployment region                       | `{projectName}-Region`                 |
| `ExtractorRoleArn`           | Lambda extractor execution role ARN     | `{projectName}-ExtractorRoleArn`        |
| `TransformerRoleArn`         | Lambda transformer execution role ARN   | `{projectName}-TransformerRoleArn`      |
| `MartRoleArn`                | Mart execution role ARN                 | `{projectName}-MartRoleArn`            |
| `DataEngineerRoleArn`        | Data engineer human role ARN            | `{projectName}-DataEngineerRoleArn`     |
| `CatalogExecutorRoleArn`     | Catalog executor role ARN               | `{projectName}-CatalogExecutorRoleArn`  |
| `AirflowCrossAccountRoleArn` | Airflow cross-account role ARN          | `{projectName}-AirflowCrossAccountRoleArn` |
| `AirflowAssumerUserName`     | Airflow assumer IAM user name           | `{projectName}-AirflowAssumerUserName`  |
| `AirflowTargetRoleArn`       | Airflow target role ARN                 | `{projectName}-AirflowTargetRoleArn`    |
| `AirflowExternalId`          | External ID for AssumeRole              | `{projectName}-AirflowExternalId`       |

## 🔐 Security & Best Practices

### Implemented

- ✅ Environment isolation
- ✅ Least privilege IAM design (planned)
- ✅ Resource naming consistency
- ✅ Configuration externalization
- ✅ Stack tagging

### Planned (Phase 2.2-2.5)

- 🔄 IAM roles with minimal permissions
- 🔄 VPC endpoints for security
- 🔄 Cost optimization policies
- 🔄 CloudTrail logging

## 🏗️ Architecture Overview

The infrastructure follows a **layered architecture pattern** with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                    Web Layer (Optional)                     │
│  CloudFront + Route53 + S3 (static assets)                 │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                   Processing Layer                          │
│  Lambda Functions (Rust) - Extract/Transform/Mart           │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                  Analytics Layer                            │
│  Athena Workgroups + Databases + Query Results             │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                  Storage Layer                              │
│  S3 Buckets (Landing/Staging/Marts) + Catalog Buckets     │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                   Security Layer                            │
│  IAM Roles + Policies + Cross-Account Access               │
└─────────────────────────────────────────────────────────────┘
```

### Key Features

- **Multi-Environment**: Complete dev/prod isolation
- **Medallion Architecture**: Landing → Staging → Marts data flow
- **Rust Lambda Functions**: High-performance data processing
- **Cross-Account Access**: Airflow integration with secure role assumption
- **Automated Lifecycle**: Cost-optimized data retention policies
- **Web Hosting**: Optional static site deployment
- **Comprehensive Monitoring**: IAM roles for observability

## 🚨 Troubleshooting

### Common Issues

1. **Context not found error**
   ```
   Error: No configuration found for environment: dev
   ```
   **Solution**: Ensure `cdk.json` has the correct `Catalunya-Data-Pipeline` context structure.

2. **Build failures**
   ```
   error TS2610: 'stackName' is defined as an accessor
   ```
   **Solution**: Use `projectName` instead of `stackName` to avoid CDK naming conflicts.

3. **AWS credentials issues**
   ```
   Error: Need to perform AWS calls but no credentials found
   ```
   **Solution**: Configure AWS CLI with `aws configure` or set environment variables.

---
