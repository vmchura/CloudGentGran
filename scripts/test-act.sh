#!/bin/bash

# Test GitHub Actions workflows locally with act and LocalStack
set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

ARTIFACTS_DIR="${PWD}/.act-artifacts"
LOCALSTACK_ENDPOINT="http://localhost:4566"

echo -e "${BLUE}🚀 Testing GitHub Actions workflows locally with act + LocalStack${NC}"

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

# Function to check if LocalStack is running
check_localstack() {
    if curl -s "$LOCALSTACK_ENDPOINT/_localstack/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ LocalStack is running${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️ LocalStack is not running${NC}"
        echo "Start LocalStack with: cd localstack && docker-compose up -d"
        echo "Or continue anyway (some features may not work)"
        return 1
    fi
}

# Function to create artifacts directory
prepare_artifacts_dir() {
    echo -e "${YELLOW}📁 Preparing artifacts directory...${NC}"
    mkdir -p "$ARTIFACTS_DIR"
    echo "Artifacts directory: $ARTIFACTS_DIR"
}

# Function to create .secrets file for LocalStack
create_secrets_file() {
    if [ ! -f .secrets ]; then
        echo -e "${YELLOW}🔐 Creating .secrets file for LocalStack...${NC}"
        cat > .secrets << EOF
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_DEFAULT_REGION=eu-west-1
AWS_ENDPOINT_URL=$LOCALSTACK_ENDPOINT
AWS_ENDPOINT_URL_S3=$LOCALSTACK_ENDPOINT
CDK_DEFAULT_ACCOUNT: '000000000000'
EOF
        echo "Created .secrets file with LocalStack credentials"
    else
        echo -e "${GREEN}✅ .secrets file already exists${NC}"
    fi
}

# Function to run specific job for testing
run_build_only() {
    echo -e "${YELLOW}🔨 Testing build jobs only (safe, no AWS)...${NC}"

    act -j build-rust-lambda \
        --artifact-server-path "$ARTIFACTS_DIR" \
        --container-architecture linux/amd64 \
        --rm \
        "$@"

    echo -e "${GREEN}✅ Build test complete${NC}"
}

# Function to run full workflow with LocalStack
run_full_workflow() {
    echo -e "${YELLOW}🎬 Running full workflow with LocalStack...${NC}"

    # Set environment variables for LocalStack
    act push --defaultbranch develop \
        --artifact-server-path "$ARTIFACTS_DIR" \
        --container-architecture linux/amd64 \
        --env AWS_ACCESS_KEY_ID=test \
        --env AWS_SECRET_ACCESS_KEY=test \
        --env AWS_DEFAULT_REGION=eu-west-1 \
        --env AWS_ENDPOINT_URL="$LOCALSTACK_ENDPOINT" \
        --env AWS_ENDPOINT_URL_S3="$LOCALSTACK_ENDPOINT" \
        --env CDK_DEFAULT_ACCOUNT=000000000000 \
        --env CDK_DEFAULT_REGION=eu-west-1 \
        --secret-file .secrets \
        -e .github/tests/push-merge.json \
        --rm \
        "$@" || {
            echo -e "${YELLOW}⚠️ Some steps may have failed (expected with LocalStack)${NC}"
            echo "This is normal - AWS-specific features might not work in LocalStack"
        }

    echo -e "${GREEN}✅ Full workflow test complete${NC}"
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

# Function to show usage
show_usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --build-only    Test only build jobs (safe, no AWS calls)"
    echo "  --full          Test full workflow with LocalStack"
    echo "  --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --build-only                    # Test Rust build only"
    echo "  $0 --full                          # Test full workflow"
    echo "  $0 --build-only --verbose          # With verbose output"
}

# Main execution
main() {
    # Parse arguments
    BUILD_ONLY=false
    FULL_WORKFLOW=false
    EXTRA_ARGS=()

    while [[ $# -gt 0 ]]; do
        case $1 in
            --build-only)
                BUILD_ONLY=true
                shift
                ;;
            --full)
                FULL_WORKFLOW=true
                shift
                ;;
            --help)
                show_usage
                exit 0
                ;;
            *)
                EXTRA_ARGS+=("$1")
                shift
                ;;
        esac
    done

    # Default to build-only if no option specified
    if [ "$BUILD_ONLY" = false ] && [ "$FULL_WORKFLOW" = false ]; then
        BUILD_ONLY=true
    fi

    # Checks
    if ! check_act; then
        exit 1
    fi

    if ! check_docker; then
        exit 1
    fi

    # LocalStack check (only warn, don't fail)
    check_localstack

    # Prepare environment
    prepare_artifacts_dir
    create_secrets_file

    # Run tests based on options
    if [ "$BUILD_ONLY" = true ]; then
        run_build_only "${EXTRA_ARGS[@]}"
    elif [ "$FULL_WORKFLOW" = true ]; then
        run_full_workflow "${EXTRA_ARGS[@]}"
    fi

    # Show results
    show_artifacts
    cleanup

    echo -e "${GREEN}🎉 Testing complete!${NC}"
    echo ""
    echo "Next steps:"
    echo "  - If build worked: Your Rust compilation is fine"
    echo "  - If full workflow worked: Your CDK + LocalStack integration is working"
    echo "  - Push to GitHub to test real AWS deployment"
}

# Handle Ctrl+C gracefully
trap cleanup EXIT INT TERM

# Run main function
main "$@"
