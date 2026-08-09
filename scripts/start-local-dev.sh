#!/bin/bash

# Catalunya Data Pipeline - Local Development Startup Script
# This script starts the complete local development environment with MiniStack integration

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

MINISTACK_STATE_VOLUME="${MINISTACK_STATE_VOLUME:-cloudgentgran-ministack-state}"
COMPOSE_FILE="docker-compose.local.yaml"

print_usage() {
    cat << EOF
Usage: $0 <command>

Commands:
    start        Start services (preserves MiniStack state, no CDK deploy)
    full-deploy  Clean start: delete MiniStack state, deploy CDK
    stop         Stop containers (preserves volumes and data)
    destroy      Remove all containers and volumes (irreversible)

S3 Data Persistence:
    Use scripts/localstack-s3-backup.sh for backup/restore of S3 bucket data
    MiniStack state reset without restart: curl -X POST http://localhost:4566/_ministack/reset
EOF
    exit 1
}

# Check prerequisites
check_prerequisites() {
    echo -e "${YELLOW}🔍 Checking prerequisites...${NC}"

    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker is not installed${NC}"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        echo -e "${RED}❌ Docker Compose is not installed${NC}"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        echo -e "${RED}❌ Docker daemon is not running${NC}"
        exit 1
    fi

    # Check for Node.js and npm for CDK deployment
    if ! command -v node &> /dev/null || ! command -v npm &> /dev/null; then
        echo -e "${RED}❌ Node.js/npm not found on host${NC}"
        echo -e "${YELLOW}⚠️  CDK deployment requires Node.js and npm${NC}"
        echo -e "${BLUE}Please install Node.js (v14+) to continue${NC}"
        exit 1
    fi

    echo -e "${GREEN}✅ Prerequisites check passed${NC}"
}

# Set environment variables
set_environment() {
    echo -e "${YELLOW}🔧 Setting up environment variables...${NC}"

    # Load persisted keys from .env (compose also reads this file)
    if [ -f ".env" ]; then
        set -a; source ".env"; set +a
    fi

    export AIRFLOW_UID=$(id -u)

    # Keys MUST come from .env (loaded above) — a new Fernet key per run would
    # make previously stored Airflow connections unreadable
    if [ -z "${AIRFLOW_FERNET_KEY:-}" ]; then
        echo -e "${RED}❌ AIRFLOW_FERNET_KEY is not set${NC}"
        echo -e "${YELLOW}Add it to .env. Generate one with:${NC}"
        echo -e "${BLUE}  python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"${NC}"
        exit 1
    fi
    if [ -z "${AIRFLOW_SECRET_KEY:-}" ]; then
        echo -e "${RED}❌ AIRFLOW_SECRET_KEY is not set${NC}"
        echo -e "${YELLOW}Add it to .env. Generate one with:${NC}"
        echo -e "${BLUE}  openssl rand -base64 32${NC}"
        exit 1
    fi
    export AIRFLOW_FERNET_KEY AIRFLOW_SECRET_KEY

    echo -e "${GREEN}✅ Environment variables set${NC}"
    echo -e "   - AIRFLOW_UID: ${AIRFLOW_UID}"
}

# Set up local development structure
setup_local_structure() {
    echo -e "${YELLOW}📦 Setting up local development structure...${NC}"

    # Remove existing dbt directory in orchestration if it exists
    if [ -d "orchestration/dbt" ]; then
        echo -e "${BLUE}🗑️  Removing existing orchestration/dbt directory${NC}"
        rm -rf orchestration/dbt
    fi

    # Copy dbt directory for local development
    echo -e "${BLUE}📁 Copying dbt/ -> orchestration/dbt/ for local development${NC}"
    cp -r dbt orchestration/dbt

    if [ -d "orchestration/dbt" ]; then
        echo -e "${GREEN}✅ Local development structure set up${NC}"
        echo -e "   📊 DBT directory size: $(du -sh orchestration/dbt | cut -f1)"
    else
        echo -e "${RED}❌ Failed to copy dbt directory${NC}"
        exit 1
    fi
}

# Clean up existing containers
cleanup() {
    echo -e "${YELLOW}🧹 Cleaning up existing containers...${NC}"

    # Stop Docker Compose services
    docker compose -f "$COMPOSE_FILE" down --remove-orphans || true

    # Clean up local development dbt copy
    if [ -d "orchestration/dbt" ]; then
        echo -e "${BLUE}🗑️  Removing local development dbt copy${NC}"
        rm -rf orchestration/dbt
    fi

    # Clean up Docker
    docker system prune -f || true

    echo -e "${GREEN}✅ Cleanup completed${NC}"
}

# Deploy CDK infrastructure on host
deploy_infrastructure() {
    echo -e "${YELLOW}🏗️  Deploying infrastructure with CDK on host...${NC}"

    # Store current directory
    local original_dir=$(pwd)

    # Ensure MiniStack is ready (HTTP 200 on health endpoint)
    echo -e "${BLUE}⏳ Waiting for MiniStack to be fully ready...${NC}"
    timeout 60s bash -c 'until curl -sf http://localhost:4566/_ministack/health > /dev/null; do sleep 2; done' || {
        echo -e "${RED}❌ MiniStack not ready for CDK deployment${NC}"
        show_logs
        exit 1
    }

    # Brief settle time for container-backed services
    echo -e "${BLUE}⏳ Ensuring MiniStack services are fully initialized...${NC}"
    sleep 5

    # Change to infrastructure directory
    cd infrastructure

    # Make script executable
    chmod +x deploy-localstack.sh

    echo -e "${BLUE}🚀 Running CDK deployment script...${NC}"
    echo -e "${BLUE}📄 Deployment output:${NC}"

    # Run the script with proper output handling and error checking
    set -o pipefail

    if bash -x deploy-localstack.sh; then
        echo -e "${GREEN}✅ Infrastructure deployment successful${NC}"
    else
        exit_code=$?
        echo -e "${RED}❌ Infrastructure deployment failed with exit code: $exit_code${NC}"
        cd "$original_dir"
        exit $exit_code
    fi

    # Return to original directory
    cd "$original_dir"

    echo -e "${GREEN}✅ CDK infrastructure deployment completed${NC}"

    # Show what was deployed
    echo -e "${BLUE}📊 Deployment summary:${NC}"
    if [ -f infrastructure/cdk-outputs.json ]; then
        echo -e "${YELLOW}CDK Outputs:${NC}"
        cat infrastructure/cdk-outputs.json | jq '.' 2>/dev/null || cat infrastructure/cdk-outputs.json
    else
        echo -e "${YELLOW}⚠️  No CDK outputs file found${NC}"
    fi
}

# Start services
start_services() {
    echo -e "${YELLOW}🐳 Starting Docker services...${NC}"

    # Start services in the correct order
    docker compose -f "$COMPOSE_FILE" up -d --build

    echo -e "${GREEN}✅ Services started${NC}"
}

# Monitor startup
monitor_startup() {
    echo -e "${YELLOW}👁️  Monitoring service startup...${NC}"

    echo -e "${BLUE}Waiting for MiniStack to be ready...${NC}"
    timeout 60s bash -c 'until curl -sf http://localhost:4566/_ministack/health > /dev/null; do sleep 2; done' || {
        echo -e "${RED}❌ MiniStack failed to start${NC}"
        show_logs
        exit 1
    }
    echo -e "${GREEN}✅ MiniStack is ready${NC}"

    echo -e "${BLUE}Waiting for Airflow to be ready...${NC}"
    timeout 300s bash -c 'until curl -sf http://localhost:8080/api/v2/monitor/health > /dev/null; do sleep 10; done' || {
        echo -e "${RED}❌ Airflow failed to start${NC}"
        show_logs
        exit 1
    }
    echo -e "${GREEN}✅ Airflow is ready${NC}"
}

# Show service status
show_status() {
    echo -e "${BLUE}📊 Service Status:${NC}"
    docker compose -f "$COMPOSE_FILE" ps

    echo -e "\n${BLUE}🔗 Service URLs:${NC}"
    echo -e "  📊 Airflow UI:     http://localhost:8080 (admin/admin)"
    echo -e "  🔧 MiniStack:      http://localhost:4566"
    echo -e "  📊 MiniStack UI:   http://localhost:4566/_ministack/health"
    echo -e "  🗄️  PostgreSQL:    localhost:5432 (airflow/airflow)"

    echo -e "\n${BLUE}🐳 Container Status:${NC}"
    docker ps --filter "name=cloudgentgran-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

# Show logs for debugging
show_logs() {
    echo -e "${RED}🔍 Showing recent logs for debugging:${NC}"
    echo -e "\n${YELLOW}MiniStack logs:${NC}"
    docker logs --tail 20 cloudgentgran-ministack 2>&1 || true
    echo -e "\n${YELLOW}Airflow logs:${NC}"
    docker logs --tail 20 cloudgentgran-airflow 2>&1 || true
}

# Validate deployment
validate_deployment() {
    echo -e "${YELLOW}🧪 Validating deployment...${NC}"

    # Check MiniStack health (HTTP 200 is sufficient; MiniStack boots in <2s)
    if ! curl -sf http://localhost:4566/_ministack/health > /dev/null; then
        echo -e "${RED}❌ MiniStack health check failed${NC}"
        return 1
    fi

    # Check deployed resources (aws CLI is bundled in the MiniStack image, but
    # docker exec does not inherit credentials/region — pass them explicitly.
    # Region must match the deploy: MiniStack isolates state per region)
    local aws_exec="docker exec -e AWS_ACCESS_KEY_ID=test -e AWS_SECRET_ACCESS_KEY=test -e AWS_DEFAULT_REGION=eu-west-1 cloudgentgran-ministack aws --endpoint-url=http://localhost:4566"
    echo -e "${BLUE}Checking deployed Lambda functions...${NC}"
    local lambda_count=$($aws_exec lambda list-functions --query 'length(Functions)' --output text 2>/dev/null || echo "0")
    if [ "$lambda_count" -ge 2 ]; then
        echo -e "${GREEN}✅ Lambda functions deployed: $lambda_count${NC}"
    else
        echo -e "${YELLOW}⚠️  Expected 2 Lambda functions, found: $lambda_count${NC}"
    fi

    # Check S3 buckets
    echo -e "${BLUE}Checking S3 buckets...${NC}"
    local bucket_count=$($aws_exec s3 ls 2>/dev/null | wc -l)
    if [ "$bucket_count" -ge 1 ]; then
        echo -e "${GREEN}✅ S3 buckets created: $bucket_count${NC}"
    else
        echo -e "${YELLOW}⚠️  No S3 buckets found${NC}"
    fi

    # Check Airflow connection (conn-id kept as localstack_default for DAG compatibility)
    echo -e "${BLUE}Checking Airflow AWS connection...${NC}"
    if timeout 30s docker exec cloudgentgran-airflow airflow connections test localstack_default >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Airflow MiniStack connection working${NC}"
    else
        echo -e "${YELLOW}⚠️  Airflow MiniStack connection test failed (may be normal during startup)${NC}"
    fi

    echo -e "${GREEN}✅ Validation completed${NC}"
}

# Validate command argument
validate_command() {
    if [[ $# -lt 1 ]]; then
        echo -e "${RED}Error: Missing command${NC}"
        print_usage
    fi
    case "$1" in
        start|full-deploy|stop|destroy)
            return 0
            ;;
        *)
            echo -e "${RED}Error: Invalid command '$1'${NC}"
            print_usage
            ;;
    esac
}

# Main function
main() {
    validate_command "$@"
    local command="$1"
    
    case "$command" in
        start)
            echo -e "${BLUE}Starting Catalunya Data Pipeline (preserving existing MiniStack state)...${NC}"
            check_prerequisites
            set_environment
            
            if [ ! -d "orchestration/dbt" ]; then
                echo -e "${YELLOW}Setting up local development structure...${NC}"
                cp -r dbt orchestration/dbt
            fi
            
            docker compose -f "$COMPOSE_FILE" up -d
            
            monitor_startup
            
            show_status
            echo -e "${GREEN}Services started. MiniStack persistence enabled (volume: ${MINISTACK_STATE_VOLUME}).${NC}"
            ;;
            
        full-deploy)
            echo -e "${BLUE}Full deploy: clearing MiniStack state and redeploying Catalunya Data Pipeline...${NC}"
            check_prerequisites
            set_environment
            
            docker compose -f "$COMPOSE_FILE" down --remove-orphans || true
            
            echo -e "${YELLOW}Removing MiniStack persisted state volume...${NC}"
            docker volume rm -f "${MINISTACK_STATE_VOLUME}" 2>/dev/null || true
            
            if [ -d "orchestration/dbt" ]; then
                rm -rf orchestration/dbt
            fi
            cp -r dbt orchestration/dbt
            
            docker compose -f "$COMPOSE_FILE" up -d
            
            echo -e "${BLUE}Waiting for MiniStack health...${NC}"
            timeout 60s bash -c 'until curl -sf http://localhost:4566/_ministack/health > /dev/null; do sleep 2; done' || {
                echo -e "${RED}MiniStack not ready${NC}"
                exit 1
            }
            sleep 5
            
            deploy_infrastructure
            validate_deployment
            
            show_status
            echo -e "${GREEN}Full deploy complete.${NC}"
            ;;
            
        stop)
            echo -e "${YELLOW}Stopping containers (preserving volumes)...${NC}"
            
            docker compose -f "$COMPOSE_FILE" down --remove-orphans
            if [ -d "orchestration/dbt" ]; then
                rm -rf orchestration/dbt
            fi
            echo -e "${GREEN}Services stopped. Volumes preserved.${NC}"
            ;;
            
        destroy)
            echo -e "${RED}Destroying all containers and volumes...${NC}"
            
            docker compose -f "$COMPOSE_FILE" down -v --remove-orphans
            
            if [ -d "orchestration/dbt" ]; then
                rm -rf orchestration/dbt
            fi
            
            rm -f infrastructure/cdk-outputs.json 2>/dev/null || true
            
            echo -e "${GREEN}All infrastructure destroyed (including ${MINISTACK_STATE_VOLUME}). Next start will be fresh.${NC}"
            ;;
    esac
}

main "$@"
