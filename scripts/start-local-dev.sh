#!/bin/bash

# Catalunya Data Pipeline - Local Development Startup Script
# This script starts the complete local development environment with LocalStack integration

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

LOCALSTACK_VOLUME_DIR="${LOCALSTACK_VOLUME_DIR:-./localstack/volume}"
COMPOSE_FILE="docker-compose.local.yaml"

print_usage() {
    cat << EOF
Usage: $0 <command>

Commands:
    start        Start services (preserves LocalStack data, no CDK deploy)
    full-deploy  Clean start: delete LocalStack state, deploy CDK, mount S3FS
    stop         Stop containers (preserves volumes and data)
    destroy      Remove all containers and volumes (irreversible)

Options:
    --with-s3fs  Also start S3FS mounts (for 'start' command only)
    --no-s3fs    Skip S3FS mounts (for 'full-deploy' command)
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

    export AIRFLOW_UID=$(id -u)
    export AIRFLOW_FERNET_KEY=${AIRFLOW_FERNET_KEY:-$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || echo "YourFernetKeyHere123456789012345678901234567890123456789012=")}
    export AIRFLOW_SECRET_KEY=${AIRFLOW_SECRET_KEY:-$(openssl rand -base64 32 2>/dev/null || echo "YourSecretKeyHere1234567890123456789012")}

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
    docker-compose -f docker-compose.local.yaml down --remove-orphans || true

    # Clean up any stale S3FS mounts
    echo -e "${YELLOW}🔧 Cleaning up stale S3FS mounts...${NC}"
    sudo umount -f ./localstack/s3-mounts/catalunya-data-dev 2>/dev/null || true
    sudo umount -f ./localstack/s3-mounts/catalunya-athena-results-dev 2>/dev/null || true
    sudo umount -f ./localstack/s3-mounts/catalunya-catalog-dev 2>/dev/null || true
    sudo umount -f ./localstack/s3-mounts/catalunya-service-dev 2>/dev/null || true

    # Remove and recreate mount directories
    sudo rm -rf ./localstack/s3-mounts/catalunya-data-dev 2>/dev/null || true
    sudo rm -rf ./localstack/s3-mounts/catalunya-athena-results-dev 2>/dev/null || true
    sudo rm -rf ./localstack/s3-mounts/catalunya-catalog-dev 2>/dev/null || true
    sudo rm -rf ./localstack/s3-mounts/catalunya-service-dev 2>/dev/null || true

    mkdir -p ./localstack/s3-mounts/catalunya-data-dev
    mkdir -p ./localstack/s3-mounts/catalunya-athena-results-dev
    mkdir -p ./localstack/s3-mounts/catalunya-catalog-dev
    mkdir -p ./localstack/s3-mounts/catalunya-service-dev

    # Set proper ownership
    sudo chown -R $USER:$USER ./localstack/s3-mounts/ 2>/dev/null || true

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

    # Ensure LocalStack is ready
    echo -e "${BLUE}⏳ Waiting for LocalStack to be fully ready...${NC}"
    timeout 180s bash -c 'until curl -s http://localhost:4566/_localstack/health | grep -q "available"; do sleep 3; done' || {
        echo -e "${RED}❌ LocalStack not ready for CDK deployment${NC}"
        show_logs
        exit 1
    }

    # Additional wait to ensure LocalStack services are fully initialized
    echo -e "${BLUE}⏳ Ensuring LocalStack services are fully initialized...${NC}"
    sleep 90

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
    docker-compose -f docker-compose.local.yaml up -d --build

    echo -e "${GREEN}✅ Services started${NC}"
}

# Monitor startup
monitor_startup() {
    echo -e "${YELLOW}👁️  Monitoring service startup...${NC}"

    echo -e "${BLUE}Waiting for LocalStack to be ready...${NC}"
    timeout 180s bash -c 'until curl -s http://localhost:4566/_localstack/health > /dev/null; do sleep 5; done' || {
        echo -e "${RED}❌ LocalStack failed to start${NC}"
        show_logs
        exit 1
    }
    echo -e "${GREEN}✅ LocalStack is ready${NC}"

    echo -e "${BLUE}Waiting for Airflow to be ready...${NC}"
    timeout 300s bash -c 'until curl -s http://localhost:8080/health > /dev/null; do sleep 10; done' || {
        echo -e "${RED}❌ Airflow failed to start${NC}"
        show_logs
        exit 1
    }
    echo -e "${GREEN}✅ Airflow is ready${NC}"
}

# Show service status
show_status() {
    echo -e "${BLUE}📊 Service Status:${NC}"
    docker-compose -f docker-compose.local.yaml ps

    echo -e "\n${BLUE}🔗 Service URLs:${NC}"
    echo -e "  📊 Airflow UI:     http://localhost:8080 (admin/admin)"
    echo -e "  🔧 LocalStack:     http://localhost:4566"
    echo -e "  📊 LocalStack UI:  http://localhost:4566/_localstack/health"
    echo -e "  🗄️  PostgreSQL:    localhost:5432 (airflow/airflow)"

    # Check S3FS status
    if docker ps --filter "name=cloudgentgran-s3fs" --filter "status=running" | grep -q cloudgentgran-s3fs; then
        echo -e "\n${BLUE}📁 S3FS Mounts (Active):${NC}"
        docker exec cloudgentgran-s3fs mountpoint -q /mnt/s3-data 2>/dev/null && \
            echo -e "  ✅ catalunya-data-dev      → ./localstack/s3-mounts/catalunya-data-dev" || true
        docker exec cloudgentgran-s3fs mountpoint -q /mnt/s3-results 2>/dev/null && \
            echo -e "  ✅ catalunya-athena-results → ./localstack/s3-mounts/catalunya-athena-results-dev" || true
        docker exec cloudgentgran-s3fs mountpoint -q /mnt/s3-catalog 2>/dev/null && \
            echo -e "  ✅ catalunya-catalog-dev   → ./localstack/s3-mounts/catalunya-catalog-dev" || true
        docker exec cloudgentgran-s3fs mountpoint -q /mnt/s3-service 2>/dev/null && \
            echo -e "  ✅ catalunya-service-dev   → ./localstack/s3-mounts/catalunya-service-dev" || true
    fi

    echo -e "\n${BLUE}🐳 Container Status:${NC}"
    docker ps --filter "name=cloudgentgran-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

# Show logs for debugging
show_logs() {
    echo -e "${RED}🔍 Showing recent logs for debugging:${NC}"
    echo -e "\n${YELLOW}LocalStack logs:${NC}"
    docker logs --tail 20 cloudgentgran-localstack 2>&1 || true
    echo -e "\n${YELLOW}Airflow logs:${NC}"
    docker logs --tail 20 cloudgentgran-airflow 2>&1 || true
}

# Validate deployment
validate_deployment() {
    echo -e "${YELLOW}🧪 Validating deployment...${NC}"

    # Check LocalStack health
    if ! curl -s http://localhost:4566/_localstack/health | grep -q '"running"'; then
        echo -e "${RED}❌ LocalStack health check failed${NC}"
        return 1
    fi

    # Check deployed resources
    echo -e "${BLUE}Checking deployed Lambda functions...${NC}"
    local lambda_count=$(docker exec cloudgentgran-localstack awslocal lambda list-functions --query 'length(Functions)' --output text 2>/dev/null || echo "0")
    if [ "$lambda_count" -ge 2 ]; then
        echo -e "${GREEN}✅ Lambda functions deployed: $lambda_count${NC}"
    else
        echo -e "${YELLOW}⚠️  Expected 2 Lambda functions, found: $lambda_count${NC}"
    fi

    # Check S3 buckets
    echo -e "${BLUE}Checking S3 buckets...${NC}"
    local bucket_count=$(docker exec cloudgentgran-localstack awslocal s3 ls 2>/dev/null | wc -l)
    if [ "$bucket_count" -ge 1 ]; then
        echo -e "${GREEN}✅ S3 buckets created: $bucket_count${NC}"
    else
        echo -e "${YELLOW}⚠️  No S3 buckets found${NC}"
    fi

    # Check Airflow connection
    echo -e "${BLUE}Checking Airflow LocalStack connection...${NC}"
    if timeout 30s docker exec cloudgentgran-airflow airflow connections test localstack_default >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Airflow LocalStack connection working${NC}"
    else
        echo -e "${YELLOW}⚠️  Airflow LocalStack connection test failed (may be normal during startup)${NC}"
    fi

    echo -e "${GREEN}✅ Validation completed${NC}"
}

# Start S3FS mounts after CDK deployment
start_s3fs_mounts() {
    echo -e "${YELLOW}📁 Starting S3FS mounts...${NC}"

    # Create mount directories if they don't exist
    mkdir -p ./localstack/s3-mounts/catalunya-data-dev
    mkdir -p ./localstack/s3-mounts/catalunya-athena-results-dev
    mkdir -p ./localstack/s3-mounts/catalunya-catalog-dev
    mkdir -p ./localstack/s3-mounts/catalunya-service-dev

    # Verify all required buckets exist before starting S3FS
    echo -e "${BLUE}🔍 Verifying S3 buckets exist before mounting...${NC}"
    local required_buckets=("catalunya-data-dev" "catalunya-athena-results-dev" "catalunya-catalog-dev" "catalunya-service-dev")
    local missing_buckets=()

    for bucket in "${required_buckets[@]}"; do
        if ! curl -s http://localhost:4566/$bucket > /dev/null 2>&1; then
            missing_buckets+=("$bucket")
        fi
    done

    if [ ${#missing_buckets[@]} -gt 0 ]; then
        echo -e "${RED}❌ Missing buckets: ${missing_buckets[*]}${NC}"
        echo -e "${YELLOW}⚠️  S3FS requires all buckets to exist. Skipping S3FS mount.${NC}"
        echo -e "${BLUE}💡 Run with 'full-deploy' to create buckets first, or ensure CDK is deployed.${NC}"
        return 1
    fi

    echo -e "${GREEN}✅ All required buckets verified${NC}"

    # Start S3FS container with profile
    docker-compose -f "$COMPOSE_FILE" --profile s3fs up -d s3fs-mounts

    # Wait for S3FS to be healthy
    echo -e "${BLUE}⏳ Waiting for S3FS mounts to be ready...${NC}"
    local max_wait=120
    local elapsed=0
    while [ $elapsed -lt $max_wait ]; do
        if docker exec cloudgentgran-s3fs mountpoint -q /mnt/s3-data 2>/dev/null; then
            echo -e "${GREEN}✅ S3FS mounts are ready${NC}"
            break
        fi
        sleep 5
        elapsed=$((elapsed + 5))
        if [ $elapsed -ge $max_wait ]; then
            echo -e "${YELLOW}⚠️  S3FS mounts may not be fully ready (timeout)${NC}"
        fi
    done

    echo -e "${BLUE}📁 S3FS mount points:${NC}"
    echo -e "   catalunya-data-dev      → ./localstack/s3-mounts/catalunya-data-dev"
    echo -e "   catalunya-athena-results → ./localstack/s3-mounts/catalunya-athena-results-dev"
    echo -e "   catalunya-catalog-dev   → ./localstack/s3-mounts/catalunya-catalog-dev"
    echo -e "   catalunya-service-dev   → ./localstack/s3-mounts/catalunya-service-dev"
}

# Stop S3FS mounts
stop_s3fs_mounts() {
    echo -e "${YELLOW}📁 Stopping S3FS mounts...${NC}"

    # Stop the S3FS container
    docker-compose -f "$COMPOSE_FILE" --profile s3fs stop s3fs-mounts 2>/dev/null || true
    docker-compose -f "$COMPOSE_FILE" --profile s3fs rm -f s3fs-mounts 2>/dev/null || true

    # Unmount any stale mounts on the host
    echo -e "${YELLOW}🔧 Unmounting any stale S3FS mounts...${NC}"
    sudo umount -f ./localstack/s3-mounts/catalunya-data-dev 2>/dev/null || true
    sudo umount -f ./localstack/s3-mounts/catalunya-athena-results-dev 2>/dev/null || true
    sudo umount -f ./localstack/s3-mounts/catalunya-catalog-dev 2>/dev/null || true
    sudo umount -f ./localstack/s3-mounts/catalunya-service-dev 2>/dev/null || true

    echo -e "${GREEN}✅ S3FS mounts stopped${NC}"
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

# Parse options
WITH_S3FS=false
NO_S3FS=false

parse_options() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --with-s3fs)
                WITH_S3FS=true
                shift
                ;;
            --no-s3fs)
                NO_S3FS=true
                shift
                ;;
            *)
                shift
                ;;
        esac
    done
}

# Main function
main() {
    validate_command "$@"
    local command="$1"
    
    parse_options "$@"
    
    case "$command" in
        start)
            echo -e "${BLUE}Starting Catalunya Data Pipeline (preserving existing LocalStack data)...${NC}"
            check_prerequisites
            set_environment
            
            if [ ! -d "orchestration/dbt" ]; then
                echo -e "${YELLOW}Setting up local development structure...${NC}"
                cp -r dbt orchestration/dbt
            fi
            
            docker-compose -f "$COMPOSE_FILE" up -d
            
            monitor_startup
            
            # Start S3FS if requested (requires existing buckets)
            if [ "$WITH_S3FS" = true ]; then
                start_s3fs_mounts || echo -e "${YELLOW}⚠️  S3FS mounts not started. Use 'full-deploy' to create buckets first.${NC}"
            fi
            
            show_status
            echo -e "${GREEN}Services started. LocalStack persistence enabled.${NC}"
            ;;
            
        full-deploy)
            echo -e "${BLUE}Full deploy: clearing LocalStack state and redeploying Catalunya Data Pipeline...${NC}"
            check_prerequisites
            set_environment
            
            # Stop any existing S3FS mounts first
            stop_s3fs_mounts
            
            docker-compose -f "$COMPOSE_FILE" down --remove-orphans || true
            
            echo -e "${YELLOW}Removing LocalStack persisted state directory...${NC}"
            sudo rm -rf "${LOCALSTACK_VOLUME_DIR}"
            mkdir -p "${LOCALSTACK_VOLUME_DIR}"
            
            if [ -d "orchestration/dbt" ]; then
                rm -rf orchestration/dbt
            fi
            cp -r dbt orchestration/dbt
            
            docker-compose -f "$COMPOSE_FILE" up -d
            
            echo -e "${BLUE}Waiting for LocalStack health...${NC}"
            timeout 180s bash -c 'until curl -s http://localhost:4566/_localstack/health | grep -q "available"; do sleep 3; done' || {
                echo -e "${RED}LocalStack not ready${NC}"
                exit 1
            }
            sleep 30
            
            deploy_infrastructure
            validate_deployment
            
            # Start S3FS mounts after successful CDK deployment (unless --no-s3fs)
            if [ "$NO_S3FS" = false ]; then
                start_s3fs_mounts || echo -e "${YELLOW}⚠️  S3FS mounts could not be started, but deployment succeeded.${NC}"
            fi
            
            show_status
            echo -e "${GREEN}Full deploy complete.${NC}"
            ;;
            
        stop)
            echo -e "${YELLOW}Stopping containers (preserving volumes)...${NC}"
            
            # Stop S3FS mounts first
            stop_s3fs_mounts
            
            docker-compose -f "$COMPOSE_FILE" down --remove-orphans
            if [ -d "orchestration/dbt" ]; then
                rm -rf orchestration/dbt
            fi
            echo -e "${GREEN}Services stopped. Volumes preserved.${NC}"
            ;;
            
        destroy)
            echo -e "${RED}Destroying all containers and volumes...${NC}"
            
            # Stop S3FS mounts first
            stop_s3fs_mounts
            
            docker-compose -f "$COMPOSE_FILE" down -v --remove-orphans
            
            echo -e "${YELLOW}Removing LocalStack volume directory...${NC}"
            sudo rm -rf "${LOCALSTACK_VOLUME_DIR}"
            
            if [ -d "orchestration/dbt" ]; then
                rm -rf orchestration/dbt
            fi
            
            rm -f infrastructure/cdk-outputs.json 2>/dev/null || true
            
            echo -e "${GREEN}All infrastructure destroyed. Next start will be fresh.${NC}"
            ;;
    esac
}

main "$@"
