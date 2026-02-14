#!/bin/bash

# Test GitHub Actions workflows locally with act and LocalStack
# Usage: ./scripts/test-act.sh [options]
set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ARTIFACTS_DIR="${PROJECT_ROOT}/.act-artifacts"
LOCALSTACK_ENDPOINT="http://localhost:4566"
EVENTS_DIR="${PROJECT_ROOT}/.github/tests"

# Available jobs in the workflow
AVAILABLE_JOBS=(
    "detect-changes"
    "build-rust-lambda"
    "build-and-test"
    "deploy-development"
    "deploy-production"
    "security-scan"
)

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  GitHub Actions Local Testing with act + LocalStack${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

# ==========================================
# UTILITY FUNCTIONS
# ==========================================

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${CYAN}[STEP]${NC} $1"; }

check_act() {
    if command -v act &> /dev/null; then
        log_info "act is installed: $(act --version 2>/dev/null || echo 'unknown version')"
        return 0
    else
        log_error "act is not installed"
        echo ""
        echo "Install options:"
        echo "  macOS:   brew install act"
        echo "  Linux:   curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash"
        echo "  Windows: scoop install act"
        return 1
    fi
}

check_docker() {
    if docker info > /dev/null 2>&1; then
        log_info "Docker is running"
        return 0
    else
        log_error "Docker is not running"
        echo "Start Docker Desktop or the Docker daemon first"
        return 1
    fi
}

check_localstack() {
    if curl -s "${LOCALSTACK_ENDPOINT}/_localstack/health" > /dev/null 2>&1; then
        log_info "LocalStack is running at $LOCALSTACK_ENDPOINT"
        return 0
    else
        log_warn "LocalStack is not running at $LOCALSTACK_ENDPOINT"
        echo ""
        echo "Start LocalStack with:"
        echo "  cd localstack && docker-compose up -d"
        echo ""
        echo "Or use --build-only to skip AWS-dependent tests"
        return 1
    fi
}

check_rust() {
    if command -v cargo &> /dev/null; then
        log_info "Rust is installed: $(rustc --version 2>/dev/null || echo 'unknown')"
        return 0
    else
        log_error "Rust is not installed"
        echo "Install Rust: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
        return 1
    fi
}

check_cargo_lambda() {
    if command -v cargo-lambda &> /dev/null; then
        log_info "cargo-lambda is installed"
        return 0
    else
        log_warn "cargo-lambda is not installed"
        echo "Install: cargo install cargo-lambda"
        return 1
    fi
}

prepare_artifacts_dir() {
    log_step "Preparing artifacts directory..."
    mkdir -p "$ARTIFACTS_DIR"
    log_info "Artifacts directory: $ARTIFACTS_DIR"
}

create_secrets_file() {
    local secrets_file="${PROJECT_ROOT}/.secrets"
    if [ ! -f "$secrets_file" ]; then
        log_step "Creating .secrets file for LocalStack..."
        cat > "$secrets_file" << EOF
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_DEFAULT_REGION=eu-west-1
AWS_ENDPOINT_URL=${LOCALSTACK_ENDPOINT}
AWS_ENDPOINT_URL_S3=${LOCALSTACK_ENDPOINT}
CDK_DEFAULT_ACCOUNT=000000000000
CDK_DEFAULT_REGION=eu-west-1
AWS_ACCOUNT_ID=000000000000
WEB_CERTIFICATE_ID=test-cert-id
EOF
        log_info "Created .secrets file with LocalStack credentials"
    else
        log_info ".secrets file already exists"
    fi
}

create_event_files() {
    mkdir -p "$EVENTS_DIR"
    
    # Push merge event (simulates PR merge to develop)
    if [ ! -f "${EVENTS_DIR}/push-merge.json" ]; then
        log_step "Creating push-merge.json event file..."
        cat > "${EVENTS_DIR}/push-merge.json" << 'EOF'
{
  "ref": "refs/heads/develop",
  "before": "0000000000000000000000000000000000000000",
  "after": "1111111111111111111111111111111111111111",
  "repository": {
    "full_name": "user/repo",
    "name": "repo",
    "owner": { "name": "user" },
    "default_branch": "develop"
  },
  "pusher": { "name": "localtester" },
  "head_commit": {
    "id": "1111111111111111111111111111111111111111",
    "message": "Merge pull request #42 from feature/test-feature",
    "timestamp": "2025-10-05T10:00:00Z",
    "author": { "name": "localtester", "email": "test@example.com" }
  }
}
EOF
        log_info "Created push-merge.json"
    fi
    
    # Direct push event (simulates direct commit to develop)
    if [ ! -f "${EVENTS_DIR}/push-direct.json" ]; then
        log_step "Creating push-direct.json event file..."
        cat > "${EVENTS_DIR}/push-direct.json" << 'EOF'
{
  "ref": "refs/heads/develop",
  "before": "0000000000000000000000000000000000000000",
  "after": "1111111111111111111111111111111111111111",
  "repository": {
    "full_name": "user/repo",
    "name": "repo",
    "owner": { "name": "user" },
    "default_branch": "develop"
  },
  "pusher": { "name": "localtester" },
  "head_commit": {
    "id": "1111111111111111111111111111111111111111",
    "message": "Add new feature",
    "timestamp": "2025-10-05T10:00:00Z",
    "author": { "name": "localtester", "email": "test@example.com" }
  }
}
EOF
        log_info "Created push-direct.json"
    fi
    
    # Pull request event
    if [ ! -f "${EVENTS_DIR}/pull-request.json" ]; then
        log_step "Creating pull-request.json event file..."
        cat > "${EVENTS_DIR}/pull-request.json" << 'EOF'
{
  "action": "opened",
  "pull_request": {
    "number": 42,
    "head": { "ref": "feature/test-feature" },
    "base": { "ref": "develop" },
    "merged": false
  },
  "repository": {
    "full_name": "user/repo",
    "name": "repo",
    "owner": { "name": "user" },
    "default_branch": "develop"
  },
  "sender": { "login": "localtester" }
}
EOF
        log_info "Created pull-request.json"
    fi
}

# ==========================================
# ACTION FUNCTIONS
# ==========================================

run_detect_changes() {
    log_step "Running detect-changes job..."
    
    local event_file="${EVENTS_DIR}/push-merge.json"
    
    act -j detect-changes \
        --artifact-server-path "$ARTIFACTS_DIR" \
        --container-architecture linux/amd64 \
        -e "$event_file" \
        --rm \
        "${EXTRA_ARGS[@]}"
    
    log_info "Detect-changes complete"
}

run_build_rust() {
    log_step "Running build-rust-lambda job..."
    
    local event_file="${EVENTS_DIR}/push-merge.json"
    
    act -j build-rust-lambda \
        --artifact-server-path "$ARTIFACTS_DIR" \
        --container-architecture linux/amd64 \
        -e "$event_file" \
        --rm \
        "${EXTRA_ARGS[@]}"
    
    log_info "Rust build complete"
    
    echo ""
    show_artifacts
    show_deploy_instructions
}

run_build_and_test() {
    log_step "Running build-and-test job (requires build-rust-lambda first)..."
    
    local event_file="${EVENTS_DIR}/push-merge.json"
    
    act -j build-and-test \
        --artifact-server-path "$ARTIFACTS_DIR" \
        --container-architecture linux/amd64 \
        -e "$event_file" \
        --rm \
        "${EXTRA_ARGS[@]}"
    
    log_info "Build and test complete"
}

run_specific_job() {
    local job_name="$1"
    
    if [[ ! " ${AVAILABLE_JOBS[*]} " =~ " ${job_name} " ]]; then
        log_error "Unknown job: $job_name"
        echo "Available jobs: ${AVAILABLE_JOBS[*]}"
        exit 1
    fi
    
    log_step "Running job: $job_name"
    
    local event_file="${EVENTS_DIR}/push-merge.json"
    
    act -j "$job_name" \
        --artifact-server-path "$ARTIFACTS_DIR" \
        --container-architecture linux/amd64 \
        -e "$event_file" \
        --rm \
        "${EXTRA_ARGS[@]}"
    
    log_info "Job $job_name complete"
}

run_full_workflow() {
    log_step "Running full workflow with LocalStack..."
    
    local event_file="${EVENTS_DIR}/push-merge.json"
    
    if [ ! -f "$event_file" ]; then
        log_error "Event file not found: $event_file"
        echo "Run with --prepare first to create event files"
        exit 1
    fi
    
    act push --defaultbranch develop \
        --artifact-server-path "$ARTIFACTS_DIR" \
        --container-architecture linux/amd64 \
        --secret-file "${PROJECT_ROOT}/.secrets" \
        -e "$event_file" \
        --rm \
        "${EXTRA_ARGS[@]}" || {
        log_warn "Some steps may have failed"
        echo "This is normal - AWS-specific features might not work in LocalStack"
    }
    
    log_info "Full workflow complete"
    show_artifacts
}

run_full_workflow_pr() {
    log_step "Running full workflow for Pull Request..."
    
    local event_file="${EVENTS_DIR}/pull-request.json"
    
    if [ ! -f "$event_file" ]; then
        log_error "Event file not found: $event_file"
        echo "Run with --prepare first to create event files"
        exit 1
    fi
    
    act pull_request --defaultbranch develop \
        --artifact-server-path "$ARTIFACTS_DIR" \
        --container-architecture linux/amd64 \
        --secret-file "${PROJECT_ROOT}/.secrets" \
        -e "$event_file" \
        --rm \
        "${EXTRA_ARGS[@]}" || {
        log_warn "Some steps may have failed"
    }
    
    log_info "PR workflow complete"
}

# Build Rust lambdas locally (without Docker/act)
build_rust_local() {
    log_step "Building Rust lambdas locally (no Docker)..."
    
    cd "$PROJECT_ROOT"
    
    if ! check_rust; then exit 1; fi
    if ! check_cargo_lambda; then exit 1; fi
    
    # Check for Zig (required by cargo-lambda)
    if ! command -v zig &> /dev/null; then
        log_warn "Zig not found, installing..."
        npm install -g @ziglang/cli || {
            log_error "Failed to install Zig"
            exit 1
        }
    fi
    
    # Build
    log_step "Compiling Rust lambdas..."
    cd lambda
    cargo lambda build --release --workspace --target x86_64-unknown-linux-gnu
    
    # Create deployment packages
    log_step "Creating deployment packages..."
    rm -rf rust_lambda_deployment rust_lambda_deployment.zip
    mkdir -p rust_lambda_deployment/social-services-transformer
    mkdir -p rust_lambda_deployment/population_municipal_greater_65
    mkdir -p rust_lambda_deployment/population_municipal_greater_65_mart
    
    cp target/lambda/social-services-transformer/bootstrap rust_lambda_deployment/social-services-transformer/
    cp target/lambda/population_municipal_greater_65/bootstrap rust_lambda_deployment/population_municipal_greater_65/
    cp target/lambda/population_municipal_greater_65_mart/bootstrap rust_lambda_deployment/population_municipal_greater_65_mart/
    
    zip -r rust_lambda_deployment.zip rust_lambda_deployment
    
    log_info "Local build complete!"
    echo ""
    ls -la rust_lambda_deployment/
    echo ""
    show_deploy_instructions
}

show_artifacts() {
    echo ""
    log_step "Artifacts created:"
    if [ -d "$ARTIFACTS_DIR" ] && [ "$(ls -A $ARTIFACTS_DIR 2>/dev/null)" ]; then
        find "$ARTIFACTS_DIR" -type f -name "*.zip" -exec ls -lh {} \;
    else
        echo "No artifacts found in $ARTIFACTS_DIR"
    fi
}

show_deploy_instructions() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  Deploying to LocalStack${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "To deploy the built artifacts to LocalStack:"
    echo ""
    echo "  1. Ensure LocalStack is running:"
    echo "     cd localstack && docker-compose up -d"
    echo ""
    echo "  2. Unzip artifacts to expected location:"
    echo "     cd ${PROJECT_ROOT}"
    echo "     unzip -o lambda/rust_lambda_deployment.zip"
    echo ""
    echo "  3. Deploy with CDK:"
    echo "     cd infrastructure"
    echo "     npm run build && npm test"
    echo "     cdklocal deploy CatalunyaDataStack-dev --require-approval never"
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
}

clean_artifacts() {
    log_step "Cleaning artifacts..."
    
    # Clean .act-artifacts
    if [ -d "$ARTIFACTS_DIR" ]; then
        rm -rf "$ARTIFACTS_DIR"
        log_info "Removed: $ARTIFACTS_DIR"
    fi
    
    # Clean local Rust build artifacts
    local rust_deployment="${PROJECT_ROOT}/lambda/rust_lambda_deployment"
    local rust_zip="${PROJECT_ROOT}/lambda/rust_lambda_deployment.zip"
    
    if [ -d "$rust_deployment" ]; then
        rm -rf "$rust_deployment"
        log_info "Removed: $rust_deployment"
    fi
    
    if [ -f "$rust_zip" ]; then
        rm -f "$rust_zip"
        log_info "Removed: $rust_zip"
    fi
    
    log_info "Cleanup complete"
}

list_jobs() {
    echo "Available jobs in the CI/CD workflow:"
    echo ""
    printf "  ${GREEN}%-25s${NC} %s\n" "JOB" "DESCRIPTION"
    printf "  %s\n" "-----------------------------------------------"
    printf "  %-25s %s\n" "detect-changes" "Detect which files changed"
    printf "  %-25s %s\n" "build-rust-lambda" "Build all Rust lambda functions"
    printf "  %-25s %s\n" "build-and-test" "Build CDK and run tests"
    printf "  %-25s %s\n" "deploy-development" "Deploy to dev (PR merge only)"
    printf "  %-25s %s\n" "deploy-production" "Deploy to prod (main branch)"
    printf "  %-25s %s\n" "security-scan" "Run security checks (PR only)"
    echo ""
    echo "Usage: $0 --job <job-name>"
}

# ==========================================
# HELP FUNCTION
# ==========================================

show_help() {
    cat << 'EOF'
Test GitHub Actions workflows locally using act and LocalStack.

USAGE:
    ./scripts/test-act.sh [OPTIONS]

OPTIONS:
    --build-only         Run only the build-rust-lambda job (default)
                         Safe to run without LocalStack/AWS credentials

    --detect-changes     Run only the detect-changes job
                         Shows which files would trigger the pipeline

    --build-and-test     Run build-and-test job (requires artifacts from build-rust-lambda)

    --full               Run full workflow with LocalStack
                         Simulates a PR merge to develop branch

    --full-pr            Run full workflow for Pull Request
                         Runs security-scan instead of deployment

    --job <name>         Run a specific job by name
                         Use --list-jobs to see available jobs

    --local-build        Build Rust lambdas locally without Docker
                         Useful for quick iteration without act overhead

    --prepare            Prepare environment without running tests
                         Creates .secrets and event JSON files

    --clean              Remove all artifacts and build outputs

    --list-jobs          List all available jobs in the workflow

    -v, --verbose        Enable verbose output

    -h, --help           Show this help message

EXAMPLES:
    # Quick test - build Rust lambdas only
    ./scripts/test-act.sh

    # Build Rust lambdas locally (faster, no Docker)
    ./scripts/test-act.sh --local-build

    # Test what would trigger on changes
    ./scripts/test-act.sh --detect-changes

    # Test a specific job
    ./scripts/test-act.sh --job build-rust-lambda --verbose

    # Full workflow test with LocalStack
    ./scripts/test-act.sh --full

    # Clean up artifacts
    ./scripts/test-act.sh --clean

WORKFLOW TRIGGER LOGIC:
    ┌─────────────────────────────────────────────────────────────┐
    │  Event                    │ Tests  │ Deploy Dev │ Deploy Prod │
    │ ─────────────────────────────────────────────────────────── │
    │  Push to develop (direct) │   ✓    │     ✗      │      ✗      │
    │  Push to develop (PR merge)│   ✓   │     ✓      │      ✗      │
    │  Push to main             │   ✓    │     ✗      │      ✓      │
    │  Pull Request             │   ✓    │     ✗      │      ✗      │
    └─────────────────────────────────────────────────────────────┘

REQUIREMENTS:
    - Docker (running)
    - act (https://github.com/nektos/act)
    - For --full: LocalStack running at http://localhost:4566
    - For --local-build: Rust, cargo-lambda, Zig

FILES CREATED:
    .secrets                    - LocalStack AWS credentials
    .github/tests/push-merge.json - Simulates PR merge event
    .github/tests/push-direct.json - Simulates direct push event
    .github/tests/pull-request.json - Simulates PR event
    .act-artifacts/             - Workflow artifacts

TROUBLESHOOTING:
    - If act fails with "permission denied": Run chmod +x scripts/test-act.sh
    - If Docker errors: Ensure Docker Desktop is running
    - If LocalStack errors: Start LocalStack first (cd localstack && docker-compose up -d)
    - If Rust build fails: Check Rust version (rustup update)

EOF
}

# ==========================================
# MAIN FUNCTION
# ==========================================

main() {
    # Parse arguments
    local MODE="build-only"
    local JOB_NAME=""
    EXTRA_ARGS=()

    while [[ $# -gt 0 ]]; do
        case $1 in
            --build-only)
                MODE="build-only"
                shift
                ;;
            --detect-changes)
                MODE="detect-changes"
                shift
                ;;
            --build-and-test)
                MODE="build-and-test"
                shift
                ;;
            --full)
                MODE="full"
                shift
                ;;
            --full-pr)
                MODE="full-pr"
                shift
                ;;
            --job)
                MODE="specific-job"
                JOB_NAME="$2"
                shift 2
                ;;
            --local-build)
                MODE="local-build"
                shift
                ;;
            --prepare)
                MODE="prepare"
                shift
                ;;
            --clean)
                MODE="clean"
                shift
                ;;
            --list-jobs)
                list_jobs
                exit 0
                ;;
            -v|--verbose)
                EXTRA_ARGS+=("--verbose")
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                EXTRA_ARGS+=("$1")
                shift
                ;;
        esac
    done

    # Handle modes that don't require checks
    case $MODE in
        clean)
            clean_artifacts
            exit 0
            ;;
        prepare)
            check_docker || exit 1
            prepare_artifacts_dir
            create_secrets_file
            create_event_files
            log_info "Environment prepared successfully"
            exit 0
            ;;
        local-build)
            build_rust_local
            exit 0
            ;;
    esac

    # Run checks for act-based modes
    if ! check_act; then exit 1; fi
    if ! check_docker; then exit 1; fi

    # Check LocalStack for full workflow
    if [[ "$MODE" == "full" || "$MODE" == "full-pr" ]]; then
        if ! check_localstack; then
            echo ""
            read -p "Continue without LocalStack? (y/N) " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 1
            fi
        fi
    fi

    # Prepare environment
    prepare_artifacts_dir
    create_secrets_file
    create_event_files

    # Run based on mode
    case $MODE in
        build-only)
            run_build_rust
            ;;
        detect-changes)
            run_detect_changes
            ;;
        build-and-test)
            run_build_and_test
            ;;
        full)
            run_full_workflow
            ;;
        full-pr)
            run_full_workflow_pr
            ;;
        specific-job)
            run_specific_job "$JOB_NAME"
            ;;
    esac

    echo ""
    log_info "Testing complete!"
}

# Handle Ctrl+C gracefully
trap 'echo ""; log_warn "Interrupted"; exit 130' INT TERM

# Run main function
main "$@"
