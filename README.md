# Catalunya Open Data Analysis Pipeline 

A data pipeline for collecting, processing, and analyzing open data from Catalunya's Open Data.
The initial focus is in elderly people (Gent Gran in Catalan) data.

## 🏗️ Architecture Overview

**Data Flow**: Catalunya APIs → Processing → Storage (3 layers) → Analytics

- **Landing Layer**: Raw JSON data from APIs
- **Staging Layer**: Cleaned and validated Parquet files
- **Marts Layer**: Analytics-ready dimensional models

## 🛠️ Technology Stack

### Core Technologies
- **Data Transformation**: DBT Core
- **Orchestration**: Apache Airflow
- **Languages**: Python, SQL, TypeScript

### Environment-Specific Stack
- **Local**: DuckDB, Docker Compose, Local storage
- **Development**: AWS Athena/S3, Dokku (on-premise Airflow)
- **Production**: AWS Athena/S3, Dokku (on-premise Airflow)

## 🌍 Environment Architecture

### Local Environment
- **Purpose**: Isolated development of individual modules
- **Storage**: Local folders/volumes, DuckDB
- **Orchestration**: Apache Airflow (Docker Compose)
- **Data Processing**: Mocked services for rapid development
- **Database**: DuckDB for testing and development

### Development Environment  
- **Purpose**: Production-like testing environment
- **Storage**: AWS S3, AWS Athena
- **Orchestration**: Apache Airflow (Dokku on-premise)
- **Data Processing**: Full AWS integration
- **Database**: AWS Athena with Glue Data Catalog

### Production Environment
- **Purpose**: Production workloads
- **Storage**: AWS S3, AWS Athena  
- **Orchestration**: Apache Airflow (Dokku on-premise)
- **Data Processing**: Full AWS integration
- **Database**: AWS Athena with Glue Data Catalog

## 📊 Current Datasets

| Dataset                                                                                                | Source | Update Frequency | Status |
|--------------------------------------------------------------------------------------------------------|--------|------------------|--------|
| [Register of entities, services, and social establishments (basic and specialized social services))](https://analisi.transparenciacatalunya.cat/en/Societat-benestar/Registre-d-entitats-serveis-i-establiments-socials/ivft-vegh/about_data) | Catalunya Open Data | Weekly           | 🔄 Planned |

## 🚀 Quick Start

### Local Development Setup

```bash
# Clone the repository
git clone https://github.com/vmchura/CloudGentGran.git
cd CloudGentGran

# Start local Airflow environment
cd orchestration
docker-compose up -d

# Access Airflow at http://localhost:8080
# Login: admin / Password: admin
```

### Development/Production Environment Setup

```bash
# Install dependencies
cd infrastructure
npm install

# Setup AWS credentials and deploy infrastructure
cd ../dbt
pip install dbt-core dbt-athena-community

# Deploy to Dokku server (Development/Production)
# Configure Dokku deployment according to environment
```

### 🔐 Prerequisites by Environment

#### Local Environment
- Docker and Docker Compose
- Git

#### Development/Production Environments
- AWS CLI configured with appropriate credentials
- Node.js 18+ (for CDK)
- Python 3.9+
- Dokku server configured for Airflow deployment

## 📁 Project Structure

```
CloudGentGran/
├── README.md                 # This file
├── docs/                     # Documentation
│   ├── architecture.md       # System architecture details
│   ├── deployment.md         # Deployment procedures
│   └── api-research.md       # Catalunya API research findings
├── orchestration/            # Apache Airflow setup
│   ├── dags/                 # Airflow DAGs
│   ├── docker-compose.yaml   # Local Airflow setup
│   ├── Dockerfile           # Airflow container
│   └── Procfile             # Dokku deployment
├── infrastructure/           # AWS CDK infrastructure code
│   ├── lib/                  # CDK stack definitions
│   ├── bin/                  # CDK app entry points
│   └── test/                 # Infrastructure tests
├── lambda/                   # AWS Lambda functions (development/production)
│   ├── extractors/           # Data extraction functions
│   ├── transformers/         # Data transformation functions
│   └── utils/                # Shared utilities
├── dbt/                      # DBT project
│   └── mart/                 # DBT models and configurations
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

### Local Environment
```bash
# Start local services
cd orchestration
docker-compose up -d

# Run DBT tests with DuckDB
cd ../dbt/mart
dbt test --target dev
```

### Development/Production Environments
```bash
# Run infrastructure tests
cd infrastructure
npm test

# Run DBT tests with Athena
cd ../dbt/mart
dbt test --target dev  # or prod
```

## 🚢 Deployment

### Local Environment
Local development runs entirely in Docker containers with no external dependencies.

### Development Environment
```bash
# Deploy AWS infrastructure
cd infrastructure
npx cdk deploy --profile dev

# Deploy Airflow to Dokku server
cd ../orchestration
git remote add dokku dokku@dev-server:catalunya-airflow
git push dokku main
```

### Production Environment
```bash
# Deploy AWS infrastructure  
cd infrastructure
npx cdk deploy --profile prod

# Deploy Airflow to Dokku server
cd ../orchestration
git remote add dokku-prod dokku@prod-server:catalunya-airflow
git push dokku-prod main
```

## 📈 Monitoring & Observability

### Local Environment
- Airflow Web UI at http://localhost:8080
- Local logs in orchestration/logs/
- DuckDB database inspection

### Development/Production Environments
- Airflow Web UI on Dokku servers
- AWS CloudWatch for infrastructure monitoring
- DBT documentation and lineage
- Custom metrics for data pipeline health

## 💰 Cost Management

### Local Environment
- No cloud costs (runs locally)
- Minimal resource usage with Docker

### Development/Production Environments  
- **S3 Storage**: Data lake storage
- **Athena Queries**: Pay per query execution
- **AWS Lambda**: Processing functions (where applicable)
- **Dokku Server**: On-premise hosting costs
- **CloudWatch**: Monitoring and logging

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