#!/bin/bash

# Test GitHub Actions workflows locally with act
set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

ARTIFACTS_DIR="${PWD}/.act-artifacts"

echo -e "${BLUE}🚀 Testing GitHub Actions workflows locally with act${NC}"

# Function to check if act is installed
check_act() {
    if command -v act &> /dev/null; then
        echo -e "${GREEN}✅ act is installed${NC}"
        return 0
    else
        echo -e "${RED}❌ act is not installed${NC}"
        echo "Install it with: curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash"
        return 1
    fi
}

# Function to check if Docker is running
check_docker() {
    if docker info > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Docker is running${NC}"
        return 0
    else
        echo -e "${RED}❌ Docker is not running${NC}"
        echo "Start Docker first"
        return 1
    fi
}

# Function to create artifacts directory
prepare_artifacts_dir() {
    echo -e "${YELLOW}📁 Preparing artifacts directory...${NC}"
    mkdir -p "$ARTIFACTS_DIR"
    echo "Artifacts directory: $ARTIFACTS_DIR"
}

# Function to run act with proper artifact server
run_act() {
    echo -e "${YELLOW}🎬 Running act with artifact server...${NC}"
    
    # Run act with artifact server enabled
    act push \
        --artifact-server-path "$ARTIFACTS_DIR" \
        --env AWS_ENDPOINT_URL=http://localhost:4566 \
        --env ACTIONS_RUNTIME_TOKEN=fake-token-for-local-testing \
        --secret-file .secrets \
        --rm
    echo -e "${GREEN}✅ act execution complete${NC}"
}

# Function to show artifacts
show_artifacts() {
    echo -e "${YELLOW}📦 Artifacts created:${NC}"
    if [ -d "$ARTIFACTS_DIR" ] && [ "$(ls -A $ARTIFACTS_DIR 2>/dev/null)" ]; then
        ls -la "$ARTIFACTS_DIR"
    else
        echo "No artifacts found"
    fi
}

# Function to clean up
cleanup() {
    echo -e "${YELLOW}🧹 Cleaning up...${NC}"
    if [ -d "$ARTIFACTS_DIR" ]; then
        echo "Artifacts directory preserved at: $ARTIFACTS_DIR"
        echo "To clean up: rm -rf $ARTIFACTS_DIR"
    fi
}

# Main execution
main() {
    if ! check_act; then
        exit 1
    fi
    
    if ! check_docker; then
        exit 1
    fi
    
    prepare_artifacts_dir
    run_act
    show_artifacts
    cleanup
    
    echo -e "${GREEN}🎉 Local GitHub Actions testing complete!${NC}"
    echo -e "${BLUE}💡 Tip: Use 'act -l' to list available jobs${NC}"
    echo -e "${BLUE}💡 Tip: Use 'act -j <job-name>' to run specific jobs${NC}"
}

# Show usage if help requested
if [[ "$1" == "--help" || "$1" == "-h" ]]; then
    echo "Usage: $0 [options]"
    echo "Test GitHub Actions workflows locally with act and artifact support"
    echo ""
    echo "Options:"
    echo "  -h, --help    Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                          # Run all workflows"
    echo "  act -j build-rust-lambda --artifact-server-path ${PWD}/.act-artifacts"
    echo "  act -j build-and-test --artifact-server-path ${PWD}/.act-artifacts"
    exit 0
fi

# Run if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
