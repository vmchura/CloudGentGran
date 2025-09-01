#!/bin/bash

# Catalunya Data Pipeline - Local Development Startup Script
# This script starts the complete local development environment with LocalStack integration

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}🚀 Starting Catalunya Data Pipeline - Local Development Environment${NC}"

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

# Clean up existing containers
cleanup() {
    echo -e "${YELLOW}🧹 Cleaning up existing containers...${NC}"

    docker-compose -f docker-compose.local.yaml down --remove-orphans || true
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
    timeout 120s bash -c 'until curl -s http://localhost:4566/_localstack/health | grep -q "running"; do sleep 3; done' || {
        echo -e "${RED}❌ LocalStack not ready for CDK deployment${NC}"
        show_logs
        exit 1
    }

    # Additional wait to ensure LocalStack services are fully initialized
    echo -e "${BLUE}⏳ Ensuring LocalStack services are fully initialized...${NC}"
    sleep 10

    # Change to infrastructure directory
    cd infrastructure

    # Make script executable and run it
    chmod +x deploy-localstack.sh

    echo -e "${BLUE}🚀 Running CDK deployment script...${NC}"
    if ./deploy-localstack.sh; then
        echo -e "${GREEN}✅ Infrastructure deployment successful${NC}"
    else
        echo -e "${RED}❌ Infrastructure deployment failed${NC}"
        cd "$original_dir"
        exit 1
    fi

    # Return to original directory
    cd "$original_dir"

    echo -e "${GREEN}✅ CDK infrastructure deployment completed${NC}"
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
    if ! curl -s http://localhost:4566/_localstack/health | grep -q '"status": "running"'; then
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

# Main function
main() {
    case "${1:-start}" in
        "start")
            check_prerequisites
            set_environment
            cleanup
            start_services
            monitor_startup
            deploy_infrastructure  # CDK deployment after LocalStack is ready
            validate_deployment
            show_status
            echo -e "\n${GREEN}🎉 Catalunya Data Pipeline is ready!${NC}"
            echo -e "${BLUE}📖 Next steps:${NC}"
            echo -e "  1. Open Airflow UI: http://localhost:8080"
            echo -e "  2. Login with: admin/admin"
            echo -e "  3. Enable the 'catalunya_social_services_localstack_pipeline' DAG"
            echo -e "  4. Trigger a manual run to test the pipeline"
            ;;
        "stop")
            echo -e "${YELLOW}🛑 Stopping Catalunya Data Pipeline...${NC}"
            docker-compose -f docker-compose.local.yaml down --remove-orphans
            echo -e "${GREEN}✅ Services stopped${NC}"
            ;;
        "restart")
            $0 stop
            sleep 5
            $0 start
            ;;
        "status")
            show_status
            ;;
        "logs")
            show_logs
            ;;
        "validate")
            validate_deployment
            ;;
        "deploy-infra")
            echo -e "${YELLOW}🏗️  Deploying infrastructure only...${NC}"
            check_prerequisites
            deploy_infrastructure
            ;;
        "clean")
            echo -e "${YELLOW}🧹 Cleaning up everything...${NC}"
            docker-compose -f docker-compose.local.yaml down --volumes --remove-orphans
            docker system prune -af
            # Clean CDK outputs
            rm -f infrastructure/cdk-outputs.json
            echo -e "${GREEN}✅ Complete cleanup finished${NC}"
            ;;
        "help"|"-h"|"--help")
            cat << EOF
Catalunya Data Pipeline - Local Development

Usage: $0 [command]

Commands:
    start          Start the complete local environment (default)
    stop           Stop all services
    restart        Restart all services
    status         Show service status and URLs
    logs           Show recent logs for debugging
    validate       Validate deployment and connections
    deploy-infra   Deploy only the CDK infrastructure (requires LocalStack running)
    clean          Complete cleanup (removes volumes and images)
    help           Show this help

Examples:
    $0              # Start everything
    $0 start        # Start everything
    $0 status       # Check status
    $0 logs         # Show logs for debugging
    $0 stop         # Stop services
    $0 deploy-infra # Deploy CDK infrastructure only

Environment Variables:
    AIRFLOW_FERNET_KEY    Custom Fernet key for Airflow (auto-generated if not set)
    AIRFLOW_SECRET_KEY    Custom secret key for Airflow (auto-generated if not set)

Prerequisites:
    - Docker and Docker Compose
    - Node.js (v14+) and npm for CDK deployment
EOF
            ;;
        *)
            echo -e "${RED}Unknown command: $1${NC}"
            $0 help
            exit 1
            ;;
    esac
}

main "$@"