# Catalunya Data Pipeline Infrastructure

This directory contains the AWS CDK TypeScript infrastructure code for the Catalunya Open Data Pipeline project.

## 📁 Project Structure

```
infrastructure/
├── bin/
│   └── infrastructure.ts      # CDK app entry point with dev/prod stacks
├── lib/
│   ├── infrastructure-stack.ts # Main Catalunya Data Stack
│   └── config.ts              # Configuration helper utilities
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
| `lambdaMemory`    | Lambda memory allocation (MB)         | `512`                | `1024`                |
| `lambdaTimeout`   | Lambda timeout (seconds)              | `300`                | `900`                 |
| `retentionPeriod` | Data retention period (days)[landing] | `7` or `ephemeral`   | `7` or `ephemeral`    |
| `retentionPeriod` | Data retention period (days)[staging] | `60`                 | `60`                  |
| `retentionPeriod` | Data retention period (days)[marts]   | `60`                 | `60`                  |
| `scheduleCron`    | Execution schedule (cron)             | `End of each friday` | `End of each friday`  |

## 📦 Stack Resources

The `CatalunyaDataStack` creates the following resources:

### Current Resources (Phase 2.1)

- **CloudFormation Outputs**: Environment, bucket name, Athena workgroup, database, Lambda prefix, region
- **Tags**: Automatic tagging with project, environment, owner, and management info

### Planned Resources (Phase 2.2-2.5)

- **S3 Buckets**: Data storage with medallion architecture (landing/staging/marts)
- **Lambda Functions**: Data extraction and transformation
- **EventBridge Rules**: Scheduled pipeline execution
- **Athena Workgroups**: Query processing and cost controls
- **IAM Roles**: Service-specific permissions with least privilege

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

| Output            | Description                 | Export Name Format              |
|-------------------|-----------------------------|---------------------------------|
| `Environment`     | Environment name (dev/prod) | `{projectName}-Environment`     |
| `BucketName`      | S3 bucket name              | `{projectName}-BucketName`      |
| `AthenaWorkgroup` | Athena workgroup name       | `{projectName}-AthenaWorkgroup` |
| `AthenaDatabase`  | Athena database name        | `{projectName}-AthenaDatabase`  |
| `LambdaPrefix`    | Lambda function prefix      | `{projectName}-LambdaPrefix`    |
| `Region`          | Deployment region           | `{projectName}-Region`          |

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

## 📈 Next Steps (Phase 2.2-2.5)

1. **S3 Infrastructure** (Phase 2.2)
    - Create medallion architecture buckets
    - Configure lifecycle policies

2. **Lambda Infrastructure** (Phase 2.3)
    - Data extraction Lambda functions
    - Execution roles and permissions
    - CloudWatch logging configuration

3. **EventBridge & Scheduling** (Phase 2.4)
    - Daily pipeline execution rules
    - Lambda triggers and permissions

4. **Athena Configuration** (Phase 2.5)
    - Workgroups and databases
    - Cost controls and query limits

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
