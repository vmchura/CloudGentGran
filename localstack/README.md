# LocalStack - Local AWS Emulator

LocalStack provides a local AWS cloud environment for development and testing of the Catalunya Data Pipeline infrastructure.

## Quick Start

### Start LocalStack Only (Empty)

For CI/CD testing with `act` or GitHub Actions simulation:

```bash
# From project root
docker-compose -f docker-compose.local.yaml up -d localstack

# Wait for LocalStack to be ready
until curl -s http://localhost:4566/_localstack/health | grep -q "running"; do
  echo "Waiting for LocalStack..."
  sleep 5
done

# Verify it's running
curl http://localhost:4566/_localstack/health | jq
```

This starts LocalStack with **no AWS resources deployed**. Use this when:
- Testing CI/CD with `scripts/test-act.sh`
- Simulating GitHub Actions locally
- Running `act` to test workflow conditions

### Start with Infrastructure Deployed

For infrastructure development (faster than act):

```bash
# 1. Start LocalStack
docker-compose -f docker-compose.local.yaml up -d localstack

# 2. Wait for readiness
sleep 10

# 3. Deploy CDK infrastructure
cd infrastructure
./deploy-localstack.sh
```

This deploys the CDK stack directly from your host machine.

---

## Architecture

### Local Development Stack

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Docker Network: cloudgentgran-local               │
│                                                                             │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────────┐   │
│  │    Airflow      │     │   LocalStack    │     │    PostgreSQL       │   │
│  │  (Port 8080)    │     │  (Port 4566)    │     │   (Port 5432)       │   │
│  │                 │     │                 │     │                     │   │
│  │ Orchestrates    │────▶│ S3, Lambda,     │     │ Airflow metadata    │   │
│  │ DAGs & Tasks    │     │ IAM, etc.       │     │                     │   │
│  └─────────────────┘     └────────┬────────┘     └─────────────────────┘   │
│                                   │                                         │
│                                   │ Persists to                             │
│                                   ▼                                         │
│                          ┌────────────────┐                                 │
│                          │ Volume:        │                                 │
│                          │ ./localstack/  │                                 │
│                          │ volume/data/   │                                 │
│                          └────────────────┘                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Persistence Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         DATA FLOW & PERSISTENCE                          │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Write Path (Lambda/Airflow/SDK):                                      │
│   ┌──────────┐    AWS SDK     ┌─────────────┐    Persist    ┌────────┐  │
│   │ Pipeline │ ─────────────▶ │  LocalStack │ ─────────────▶ │ Volume │  │
│   │ (write)  │                │     S3      │               │  Disk  │  │
│   └──────────┘                └─────────────┘               └────────┘  │
│                                                                          │
│   Read Path (Verification):                                             │
│   ┌──────────┐    AWS CLI     ┌─────────────┐                            │
│   │  User    │ ─────────────▶ │  LocalStack │  ✅ Verify S3 data        │
│   │ (verify) │                │     S3      │                            │
│   └──────────┘                └─────────────┘                            │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### Docker Volumes

| Volume | Type | Purpose |
|--------|------|---------|
| `./localstack/volume` | Bind Mount | LocalStack persistence (S3 data, Lambdas, IAM, etc.) |
| `cloudgentgran-postgres-data` | Named Volume | Airflow PostgreSQL data |

### S3 Buckets

| Bucket | Purpose |
|--------|---------|
| `catalunya-data-dev` | Main data lake (landing, staging, marts) |
| `catalunya-catalog-dev` | Reference data (municipals, service types) |
| `catalunya-athena-results-dev` | Athena query results |
| `catalunya-service-dev` | Service-specific data |

---

## Usage Patterns

### Pattern 1: CI/CD Testing with act

Test GitHub Actions workflows locally without real AWS:

```bash
# Start empty LocalStack
docker-compose -f docker-compose.local.yaml up -d localstack

# Run full CI/CD simulation (builds Rust, deploys CDK)
./scripts/test-act.sh --full

# Or test specific jobs
./scripts/test-act.sh --build-only       # Just Rust build
./scripts/test-act.sh --detect-changes   # Test change detection
```

**Note:** `test-act.sh --full` runs everything including CDK deployment inside Docker containers.

### Pattern 2: Fast Infrastructure Iteration

Quick CDK development without Docker overhead:

```bash
# Start LocalStack
docker-compose -f docker-compose.local.yaml up -d localstack

# Build Rust lambdas locally (if needed)
./scripts/test-act.sh --local-build

# Deploy infrastructure
cd infrastructure && ./deploy-localstack.sh

# Make changes and redeploy
npm run build && npx cdklocal deploy CatalunyaDataStack-dev --require-approval never
```

### Pattern 3: Full Local Development (Airflow + LocalStack)

Complete local environment with orchestration:

```bash
./scripts/start-local-dev.sh start
```

This includes Airflow, LocalStack, and PostgreSQL.

---

## Available Endpoints

| Service | URL | Description |
|---------|-----|-------------|
| LocalStack Gateway | http://localhost:4566 | Main API endpoint |
| Health Check | http://localhost:4566/_localstack/health | Service status |
| S3 (via endpoint) | http://localhost:4566 | S3 API |
| Lambda (via endpoint) | http://localhost:4566 | Lambda API |

---

## AWS CLI Commands

Use `awslocal` or `aws --endpoint-url`:

```bash
# Using awslocal (if installed)
awslocal s3 ls
awslocal lambda list-functions

# Using standard AWS CLI
aws --endpoint-url=http://localhost:4566 s3 ls
aws --endpoint-url=http://localhost:4566 lambda list-functions
aws --endpoint-url=http://localhost:4566 iam list-roles
```

---

## Cleanup

### Stop LocalStack Only

```bash
docker-compose -f docker-compose.local.yaml stop localstack
```

### Stop and Remove LocalStack Container

```bash
docker-compose -f docker-compose.local.yaml down localstack
```

### Remove All LocalStack Data (Full Reset)

```bash
# Stop and remove container + volumes
docker-compose -f docker-compose.local.yaml down -v localstack

# Clear LocalStack cache (if exists)
rm -rf ./localstack/volume/cache/*

# Restart fresh
docker-compose -f docker-compose.local.yaml up -d localstack
```

### Clean All Docker Resources

```bash
# Stop all project containers
docker-compose -f docker-compose.local.yaml down

# Remove all stopped containers, unused networks, images
docker system prune -f

# Nuclear option - remove everything (careful!)
docker-compose -f docker-compose.local.yaml down -v --remove-orphans
docker system prune -af --volumes
```

---

## Troubleshooting

### LocalStack Won't Start

```bash
# Check Docker is running
docker info

# Check for port conflicts
lsof -i :4566

# Check logs
docker logs cloudgentgran-localstack
```

### CDK Deployment Fails

```bash
# Ensure LocalStack is healthy
curl http://localhost:4566/_localstack/health

# Check CDK can connect
cd infrastructure
npx cdklocal synth CatalunyaDataStack-dev

# Try fresh bootstrap
npx cdklocal bootstrap
```

### Act Cannot Connect to LocalStack

The `act` runner runs inside its own Docker container. Use `host.docker.internal` instead of `localhost`:

```bash
# In .secrets file or environment
AWS_ENDPOINT_URL=http://host.docker.internal:4566
```

Or ensure both are on the same Docker network:

```bash
docker network inspect cloudgentgran-local
```

### Rust Lambda Build Issues

```bash
# Build Rust locally without act
./scripts/test-act.sh --local-build

# Check prerequisites
rustc --version
cargo lambda --version
zig version
```

---

## Environment Variables

Key environment variables used by LocalStack:

| Variable | Default | Description |
|----------|---------|-------------|
| `AWS_ACCESS_KEY_ID` | `test` | Fake AWS key |
| `AWS_SECRET_ACCESS_KEY` | `test` | Fake AWS secret |
| `AWS_DEFAULT_REGION` | `eu-west-1` | Target region |
| `AWS_ENDPOINT_URL` | `http://localhost:4566` | LocalStack endpoint |

---

## Files Reference

| File | Purpose |
|------|---------|
| `docker-compose.local.yaml` | Docker Compose with LocalStack + Airflow |
| `infrastructure/deploy-localstack.sh` | CDK deployment script for LocalStack |
| `scripts/test-act.sh` | GitHub Actions testing with act |
| `scripts/start-local-dev.sh` | Full local development environment |
| `scripts/localstack-s3-backup.sh` | S3 data backup/restore script |
| `localstack/s3-backup/` | S3 backup storage |

---

## First-Time Setup / Reset

For a clean start:

```bash
# 1. Stop all containers
docker-compose -f docker-compose.local.yaml down

# 2. Remove old volumes (optional, for full reset)
docker volume rm cloudgentgran-postgres-data cloudgentgran-airflow-dbt-profiles 2>/dev/null || true

# 3. Start fresh
docker-compose -f docker-compose.local.yaml up -d
```

---

## Data Persistence (Community Edition)

LocalStack Community Edition does **NOT persist data** between container restarts. S3 data, Lambda functions, and other resources are lost when containers stop.

### Solution: S3 Backup/Restore Script

Use the provided script to backup and restore S3 data:

```bash
# Backup all S3 buckets to local filesystem
./scripts/localstack-s3-backup.sh backup

# List available backups
./scripts/localstack-s3-backup.sh list

# Restore all buckets from backup
./scripts/localstack-s3-backup.sh restore

# Backup/restore specific bucket
./scripts/localstack-s3-backup.sh backup catalunya-data-dev
./scripts/localstack-s3-backup.sh restore catalunya-data-dev
```

### Recommended Workflow

```bash
# 1. Start LocalStack
docker-compose -f docker-compose.local.yaml up -d

# 2. Restore data from previous session (if any)
./scripts/localstack-s3-backup.sh restore

# 3. Deploy infrastructure (first time only)
cd infrastructure && ./deploy-localstack.sh

# 4. Do your development work...

# 5. Before stopping, backup your data
./scripts/localstack-s3-backup.sh backup

# 6. Stop containers
docker-compose -f docker-compose.local.yaml down
```

### Backup Location

Backups are stored in `./localstack/s3-backup/`:
```
localstack/s3-backup/
├── catalunya-data-dev/
│   ├── landing/...
│   ├── staging/...
│   └── marts/...
├── catalunya-catalog-dev/
│   └── ...
└── ...
```
