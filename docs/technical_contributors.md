# Technical Contributors Guide

## 🚀 Environment Setup

### Prerequisites

#### Local Development

- Docker and Docker Compose
- Git
- Python 3.12+

#### AWS Development

- AWS CLI configured
- Node.js 18+ (for CDK)
- Python 3.12+
- Rust stable toolchain (for Lambda development)
- Access to Dokku server

### Local Setup

```bash
git clone https://github.com/vmchura/CloudGentGran.git
cd CloudGentGran

./scripts/start-local-dev.sh
```

Access Airflow at http://localhost:8080 (admin/admin) or search logs for admin user

## 📁 Project Structure

```
CloudGentGran/
├── orchestration/       # Apache Airflow
├── infrastructure/      # AWS CDK
├── lambda/             # AWS Lambda functions
├── rust_lambda_deployment/  # Compiled Lambda rust binaries (should be created before deploying locally)
├── dbt/                
├── observable/         
└── scripts/            # Utility scripts
```

## 🔧 Development Workflow

### Branches

- `main`: Production
- `develop`: Integration
- `feature/*`: Features
- `hotfix/*`: Fixes

### Process

1. Fork repository
2. Create feature branch
3. Make changes
4. Test locally
5. Submit PR to `develop`

## 🚢 Deployment of AWS Infrastructure

Implemented in GitHub Actions with the file .github/workflows/ci-cd.yml, triggered by a merge into develop and main branches.

## 🚢 Deployment of Apache Airflow

### Development

Set up a dokku server the execute the script:

```bash
AIRFLOW_USER_PASSWORD_DEV=admin ./scripts/deploy/deploy-orchestration.sh development '<<DOKKU SERVER>>' '<<SSH KEY NAME>>' '<<DOKKU_DOMAIN>>'
```

### Production

```bash
AIRFLOW_USER_PASSWORD_PROD=admin ./scripts/deploy/deploy-orchestration.sh production '<<DOKKU SERVER>>' '<<SSH KEY NAME>>' '<<DOKKU_DOMAIN>>'
```

## 📝 Code Standards

- Python: PEP 8
- SQL: dbt style guide
