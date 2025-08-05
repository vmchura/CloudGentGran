# Catalunya Open Data Analysis Pipeline 

A modern, cloud-native data pipeline for collecting, processing, and analyzing open data from Catalunya's Open Data.
The initial focus is in elderly people (Gent Gran in Catalan) data.

## 🏗️ Architecture Overview

**Data Flow**: Catalunya APIs → AWS Lambda → S3 (3 layers) → GitHub Actions (DBT) → S3

- **Landing Layer** (`s3://bucket/landing/`): Raw JSON data from APIs
- **Staging Layer** (`s3://bucket/staging/`): Cleaned and validated Parquet files
- **Marts Layer** (`s3://bucket/marts/`): Analytics-ready dimensional models

## 🛠️ Technology Stack

- **Cloud Platform**: AWS (Lambda, S3, Athena, EventBridge)
- **Data Transformation**: DBT Core
- **Infrastructure**: AWS CDK (TypeScript)
- **CI/CD**: GitHub Actions
- **Languages**: Python (Lambda), SQL (DBT), TypeScript (CDK)

## 📊 Current Datasets

| Dataset                                                                                                | Source | Update Frequency | Status |
|--------------------------------------------------------------------------------------------------------|--------|------------------|--------|
| [Register of entities, services, and social establishments (basic and specialized social services))](https://analisi.transparenciacatalunya.cat/en/Societat-benestar/Registre-d-entitats-serveis-i-establiments-socials/ivft-vegh/about_data) | Catalunya Open Data | Weekly           | 🔄 Planned |

## 🚀 Quick Start

### Prerequisites

- AWS CLI configured with appropriate credentials
- Node.js 18+ (for CDK)
- Python 3.9+ (for Lambda functions)
- Git

### Development Setup

```bash
# Clone the repository
git clone https://github.com/vmchura/CloudGentGran.git
cd CloudGentGran

# Install CDK dependencies and bootstrap AWS
cd infrastructure
npm install
# command used to start the infrastructure: npx cdk init app --language typescript

# Install Lambda dependencies (when developing Lambda functions)
cd ../lambda
pip install -r requirements.txt -t .

# Install DBT dependencies (when working with DBT models)
cd ../dbt
pip install dbt-core dbt-athena-community
```

### Environment Configuration

1. Copy environment template:
   ```bash
   cp .env.example .env
   ```

2. Configure your environment variables:
   ```bash
   # AWS Configuration
   AWS_PROFILE=your-profile
   AWS_REGION=eu-west-1
   
   # Project Configuration
   PROJECT_NAME=catalunya-data-pipeline
   ENVIRONMENT=development
   ```

### 🔐 AWS Credentials Setup

Configure GitHub repository secrets for AWS deployment:

#### Quick Setup
```bash
./scripts/setup/configure-aws-secrets.sh
```

#### Manual Setup
```bash
# Development Environment
gh secret set AWS_ACCESS_KEY_ID_DEV --body "your_dev_access_key_id"
gh secret set AWS_SECRET_ACCESS_KEY_DEV --body "your_dev_secret_access_key"
gh secret set AWS_REGION_DEV --body "eu-west-1"

# Production Environment
gh secret set AWS_ACCESS_KEY_ID_PROD --body "your_prod_access_key_id"
gh secret set AWS_SECRET_ACCESS_KEY_PROD --body "your_prod_secret_access_key"
gh secret set AWS_REGION_PROD --body "eu-west-1"
```

**Required Secrets:**
- `AWS_ACCESS_KEY_ID_DEV` / `AWS_ACCESS_KEY_ID_PROD` - AWS Access Key IDs
- `AWS_SECRET_ACCESS_KEY_DEV` / `AWS_SECRET_ACCESS_KEY_PROD` - AWS Secret Access Keys  
- `AWS_REGION_DEV` / `AWS_REGION_PROD` - AWS regions (e.g., `eu-west-1`)

📖 **Detailed Instructions**: [docs/aws-secrets-setup.md](docs/aws-secrets-setup.md)

## 📁 Project Structure

```
CloudGentGran/
├── README.md                 # This file
├── docs/                     # Documentation
│   ├── architecture.md       # System architecture details
│   ├── deployment.md         # Deployment procedures
│   └── api-research.md       # Catalunya API research findings
├── infrastructure/           # AWS CDK infrastructure code
│   ├── lib/                  # CDK stack definitions
│   ├── bin/                  # CDK app entry points
│   └── test/                 # Infrastructure tests
├── lambda/                   # AWS Lambda functions
│   ├── extractors/           # Data extraction functions
│   ├── transformers/         # Data transformation functions
│   └── utils/                # Shared utilities
├── dbt/                      # DBT project
│   ├── models/               # SQL transformation models
│   ├── macros/               # Reusable SQL macros
│   └── tests/                # Data quality tests
├── .github/
│   ├── workflows/            # GitHub Actions CI/CD
│   └── ISSUE_TEMPLATE.md     # Issue templates
├── scripts/                  # Utility scripts
│   ├── setup/                # Environment setup scripts
│   ├── deploy/               # Deployment scripts
│   └── maintenance/          # Maintenance utilities
└── .gitignore               # Git ignore rules
```

## 🔧 Development Workflow

### Branch Strategy

- `main`: Production-ready code
- `develop`: Integration branch for features
- `feature/*`: Feature development branches
- `hotfix/*`: Critical production fixes

### Making Changes

1. Create a feature branch:
   ```bash
   git checkout -b feature/new-dataset-integration
   ```

2. Make your changes and test locally

3. Submit a pull request to `develop`

4. After review and CI passes, merge to `develop`

5. Regular releases merge `develop` → `main`

## 🧪 Testing

```bash
# Run all tests
make test

# Run specific test suites
make test-lambda      # Lambda function tests
make test-dbt         # DBT model tests
make test-infrastructure  # CDK infrastructure tests
```

## 🚢 Deployment

### Development Environment
```bash
make deploy-dev
```

### Production Environment
```bash
make deploy-prod
```

See [docs/deployment.md](docs/deployment.md) for detailed deployment procedures.

## 📈 Monitoring & Observability

- **Logs**: CloudWatch Logs for all Lambda functions
- **Metrics**: Custom CloudWatch metrics for data pipeline health
- **Alerts**: SNS notifications for pipeline failures
- **Dashboards**: CloudWatch Dashboard for operational overview

## 💰 Cost Management

Current monthly costs (development environment):
- **S3 Storage**: ~$2-5/month
- **Lambda Executions**: ~$1-3/month
- **Athena Queries**: ~$1-2/month
- **CloudWatch**: ~$1-2/month
- **Total**: <$15/month

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: Check the [docs/](docs/) folder
- **Issues**: Create a GitHub issue
- **Discussions**: Use GitHub Discussions for questions

## 🗺️ Roadmap

- [ ] **Phase 1**: Foundation Setup
- [ ] **Phase 2**: Infrastructure as Code (AWS CDK)
- [ ] **Phase 3**: Data Extraction Layer (Lambda)
- [ ] **Phase 4**: DBT Project Setup
- [ ] **Phase 5**: Data Transformation Models
- [ ] **Phase 6**: GitHub Actions Workflow
- [ ] **Phase 7**: Integration and Testing
- [ ] **Phase 8**: Production Deployment
- [ ] **Phase 9**: Monitoring and Maintenance

---

**Last Updated**: August 2025  
**Maintainer**: vmchura