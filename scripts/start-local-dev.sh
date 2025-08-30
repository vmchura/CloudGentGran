#!/bin/bash
# Catalunya Data Pipeline - Local Development Startup Script
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_NAME="Catalunya Data Pipeline"
COMPOSE_FILE="docker-compose.local.yaml"

echo -e "${BLUE}🚀 Starting ${PROJECT_NAME} - Local Development Environment${NC}"

# Check prerequisites
check_prerequisites() {
    echo -e "${YELLOW}🔍 Checking prerequisites...${NC}"

    command -v docker >/dev/null 2>&1 || {
        echo -e "${RED}❌ Docker is required but not installed${NC}"; exit 1;
    }

    command -v docker-compose >/dev/null 2>&1 || {
        echo -e "${RED}❌ Docker Compose is required but not installed${NC}"; exit 1;
    }

    # Check if Docker daemon is running
    if ! docker info > /dev/null 2>&1; then
        echo -e "${RED}❌ Docker daemon is not running${NC}"
        exit 1
    fi

    echo -e "${GREEN}✅ Prerequisites check passed${NC}"
}

# Clean up function
cleanup() {
    echo -e "${YELLOW}🧹 Cleaning up previous containers...${NC}"
    docker-compose -f ${COMPOSE_FILE} down --remove-orphans || true
}

# Start services
start_services() {
    echo -e "${YELLOW}🚀 Starting services...${NC}"

    # Pull latest images
    echo -e "${YELLOW}📥 Pulling latest images...${NC}"
    docker-compose -f ${COMPOSE_FILE} pull

    # Start services
    docker-compose -f ${COMPOSE_FILE} up -d

    echo -e "${GREEN}✅ Services started successfully${NC}"
}

# Wait for services to be healthy
wait_for_services() {
    echo -e "${YELLOW}⏳ Waiting for services to be ready...${NC}"

    # Wait for LocalStack
    echo -e "${BLUE}   Waiting for LocalStack...${NC}"
    timeout 120 bash -c 'until curl -s http://localhost:4566/_localstack/health | grep -q "running"; do sleep 2; done'
    echo -e "${GREEN}   ✅ LocalStack is ready${NC}"

    # Wait for Airflow
    echo -e "${BLUE}   Waiting for Airflow...${NC}"
    timeout 180 bash -c 'until curl -s http://localhost:8080/health | grep -q "healthy"; do sleep 5; done'
    echo -e "${GREEN}   ✅ Airflow is ready${NC}"

    echo -e "${GREEN}✅ All services are healthy${NC}"
}

# Deploy infrastructure to LocalStack
deploy_infrastructure() {
    echo -e "${YELLOW}🏗️ Deploying infrastructure to LocalStack...${NC}"

    cd infrastructure
    if [ -f "deploy-localstack.sh" ]; then
        ./deploy-localstack.sh
    else
        echo -e "${YELLOW}⚠️ deploy-localstack.sh not found, skipping infrastructure deployment${NC}"
    fi
    cd ..

    echo -e "${GREEN}✅ Infrastructure deployment completed${NC}"
}

# Show service information
show_info() {
    echo -e "${GREEN}"
    echo "🎉 Catalunya Data Pipeline Local Environment is Ready!"
    echo ""
    echo "📊 Services Available:"
    echo "   • Airflow UI:    http://localhost:8080 (admin/admin)"
    echo "   • PostgreSQL:    localhost:5432 (airflow/airflow)"
    echo "   • LocalStack:    http://localhost:4566"
    echo ""
    echo "🔧 LocalStack Health: http://localhost:4566/_localstack/health"
    echo ""
    echo "💡 Useful Commands:"
    echo "   • View logs:     docker-compose -f ${COMPOSE_FILE} logs -f [service]"
    echo "   • Stop all:      docker-compose -f ${COMPOSE_FILE} down"
    echo "   • Restart:       docker-compose -f ${COMPOSE_FILE} restart [service]"
    echo ""
    echo "🏗️ AWS CLI with LocalStack:"
    echo "   aws --endpoint-url=http://localhost:4566 s3 ls"
    echo "   aws --endpoint-url=http://localhost:4566 lambda list-functions"
    echo -e "${NC}"
}

# Main execution
main() {
    case "${1:-start}" in
        "start")
            check_prerequisites
            cleanup
            start_services
            wait_for_services
            deploy_infrastructure
            show_info
            ;;
        "stop")
            echo -e "${YELLOW}🛑 Stopping Catalunya Data Pipeline...${NC}"
            docker-compose -f ${COMPOSE_FILE} down
            echo -e "${GREEN}✅ Stopped successfully${NC}"
            ;;
        "restart")
            echo -e "${YELLOW}🔄 Restarting Catalunya Data Pipeline...${NC}"
            docker-compose -f ${COMPOSE_FILE} restart
            wait_for_services
            show_info
            ;;
        "logs")
            docker-compose -f ${COMPOSE_FILE} logs -f ${2:-}
            ;;
        "status")
            docker-compose -f ${COMPOSE_FILE} ps
            ;;
        *)
            echo "Usage: $0 {start|stop|restart|logs [service]|status}"
            exit 1
            ;;
    esac
}

# Set working directory to script's parent
cd "$(dirname "$0")/.."

main "$@"