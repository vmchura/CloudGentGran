# Catalunya Data Pipeline Infrastructure

AWS CDK TypeScript infrastructure for the Catalunya Open Data Pipeline project with multi-environment support.

## 🏗️ Architecture

Multi-environment architecture with complete dev/prod isolation:
- **Environment Isolation**: Separate dev and prod stacks
- **Configuration-Driven**: Environment-specific settings in `cdk.json`
- **Medallion Architecture**: Landing → Staging → Marts data flow
- **Least Privilege**: IAM roles with minimal permissions
- **Export Values**: Stack outputs for cross-stack references

### Layer Architecture

```
Web Layer                   CloudFront + Route53 + S3 (static)
Processing Layer            Lambda Functions (Rust) - Extract/Transform/Mart
Analytics Layer             Athena Workgroups + Databases
Storage Layer               S3 Buckets (Landing/Staging/Marts) + Catalog
Security Layer              IAM Roles + Policies + Cross-Account Access
```

## 📁 Structure

```
infrastructure/
├── bin/infrastructure.ts       # CDK app entry point
├── lib/                        # Infrastructure constructs
│   ├── infrastructure-stack.ts # Main stack
│   ├── config.ts              # Configuration utilities
│   ├── iam-construct.ts       # IAM roles and policies
│   ├── s3-construct.ts        # S3 buckets with lifecycle policies
│   ├── lambda-construct.ts    # Lambda functions
│   ├── analytics-construct.ts # Athena workgroups and databases
│   ├── catalog-construct.ts   # Data catalog functions
│   ├── glue-construct.ts      # Glue jobs and crawlers
│   └── web-construct.ts       # CloudFront and Route53 (optional)
├── test/infrastructure.test.ts # Unit tests
├── cdk.json                   # CDK configuration
├── package.json               # Dependencies
└── tsconfig.json             # TypeScript config
```

## 🚀 Setup

### Prerequisites
- Node.js 18+
- AWS CLI configured
- AWS CDK CLI: `npm install -g aws-cdk`

### Installation
```bash
cd infrastructure
npm install
```

### Development
```bash
npm run build      # Build TypeScript
npm test           # Run unit tests
npx cdk list       # List all stacks
npx cdk synth CatalunyaDataStack-dev  # Synthesize dev stack
```

## ⚙️ Configuration

Configuration is managed in `cdk.json` under the `Catalunya-Data-Pipeline` context:

| Parameter | Description | Dev | Prod |
|-----------|-------------|-----|------|
| `region` | AWS region | `eu-west-1` | `eu-west-1` |
| `bucketName` | Main data bucket | `catalunya-data-dev` | `catalunya-data-prod` |
| `catalogBucketName` | Catalog bucket | `catalunya-catalog-dev` | `catalunya-catalog-prod` |
| `serviceBucketName` | Service bucket | `catalunya-service-dev` | `catalunya-service-prod` |
| `lambdaMemory` | Lambda memory (MB) | `512` | `1024` |
| `lambdaTimeout` | Lambda timeout (seconds) | `300` | `900` |
| `retentionPeriod` | Landing retention (days) | `7` | `7` |
| `retentionPeriod` | Staging/Marts retention (days) | `60` | `60` |
| `webDomain` | Web domain | `analitica.academy/` | `analitica.academy/` |
| `webSubdomain` | Web subdomain | `dev` | `` |

## 📦 Resources

### Infrastructure Components

**Storage**
- S3 buckets with medallion architecture (landing/staging/marts)
- Landing: 7-day retention, Staging/Marts: 60-day IA transition
- Athena results bucket for query outputs

**Processing**
- Rust-based Lambda functions for data extraction/transform/mart generation
- Social services transformer, population municipal processors

**Security**
- IAM roles with least privilege (Extractor, Transformer, Mart, Monitoring)
- Data engineer human access role
- Airflow cross-account execution role

**Analytics**
- Athena workgroups with cost controls
- Database for data catalog
- Glue crawlers for schema discovery

**Optional**
- Web infrastructure (CloudFront + Route53) - requires `WEB_CERTIFICATE_ID`

## 🌍 Environments

| Environment | Stack Name | Prefix | Purpose |
|-------------|------------|--------|---------|
| `dev` | `CatalunyaDataStack-dev` | `catalunya-dev` | Testing/development |
| `prod` | `CatalunyaDataStack-prod` | `catalunya-prod` | Live data processing |

## 🚀 Deployment

Via GitHub Actions

## 🧪 Testing

```bash
npm test                              # Run all tests
npm run test -- --watch              # Watch mode
npm run test -- --coverage           # With coverage
```

**Test Coverage**
- Stack synthesis validation
- Environment configuration
- Output validation
- Error handling


## 🔐 Security

**Implemented**
- ✅ Environment isolation
- ✅ Least privilege IAM design
- ✅ Resource naming consistency
- ✅ Configuration externalization
- ✅ Stack tagging

**Planned**
- 🔄 Cost optimization policies
- 🔄 CloudTrail logging

