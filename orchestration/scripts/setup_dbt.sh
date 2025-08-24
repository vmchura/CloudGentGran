#!/bin/bash

# Catalunya Data Pipeline - DBT Setup Script
# This script sets up DBT for the orchestration environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

# Configuration
ENVIRONMENT=${ENVIRONMENT:-development}
DBT_PROFILES_DIR=${DBT_PROFILES_DIR:-/home/airflow/.dbt}
DBT_PROJECT_DIR=${DBT_PROJECT_DIR:-/opt/airflow/dbt_mart}
ORCHESTRATION_DIR="/opt/airflow"

# Function to check if DBT is installed
check_dbt_installation() {
    log "Checking DBT installation..."

    if ! command -v dbt &> /dev/null; then
        error "DBT is not installed!"
        exit 1
    fi

    DBT_VERSION=$(dbt --version | head -1 | grep -o '[0-9]\+\.[0-9]\+\.[0-9]\+')
    log "DBT version: $DBT_VERSION"

    # Check for required adapters
    if dbt --version | grep -q "duckdb"; then
        log "DBT DuckDB adapter found"
    else
        warn "DBT DuckDB adapter not found"
    fi

    if dbt --version | grep -q "athena"; then
        log "DBT Athena adapter found"
    else
        warn "DBT Athena adapter not found"
    fi
}

# Function to setup DBT profiles directory
setup_profiles_directory() {
    log "Setting up DBT profiles directory..."

    # Create profiles directory if it doesn't exist
    mkdir -p "$DBT_PROFILES_DIR"

    # Set proper ownership
    if [ "$(whoami)" = "root" ]; then
        chown -R airflow:airflow "$DBT_PROFILES_DIR"
    fi

    # Set proper permissions
    chmod 755 "$DBT_PROFILES_DIR"

    log "DBT profiles directory created at: $DBT_PROFILES_DIR"
}

# Function to copy appropriate profile based on environment
setup_dbt_profiles() {
    log "Setting up DBT profiles for environment: $ENVIRONMENT"

    PROFILE_SOURCE=""

    if [ "$ENVIRONMENT" = "production" ]; then
        PROFILE_SOURCE="$ORCHESTRATION_DIR/dbt_profiles/profiles_prod.yml"
        log "Using production profile (Athena)"
    else
        PROFILE_SOURCE="$ORCHESTRATION_DIR/dbt_profiles/profiles_dev.yml"
        log "Using development profile (DuckDB)"
    fi

    if [ -f "$PROFILE_SOURCE" ]; then
        cp "$PROFILE_SOURCE" "$DBT_PROFILES_DIR/profiles.yml"
        log "Profile copied successfully"

        # Set proper permissions
        chmod 644 "$DBT_PROFILES_DIR/profiles.yml"

        if [ "$(whoami)" = "root" ]; then
            chown airflow:airflow "$DBT_PROFILES_DIR/profiles.yml"
        fi
    else
        error "Profile source not found: $PROFILE_SOURCE"
        exit 1
    fi
}

# Function to validate DBT project
validate_dbt_project() {
    log "Validating DBT project..."

    if [ ! -d "$DBT_PROJECT_DIR" ]; then
        error "DBT project directory not found: $DBT_PROJECT_DIR"
        exit 1
    fi

    if [ ! -f "$DBT_PROJECT_DIR/dbt_project.yml" ]; then
        error "dbt_project.yml not found in: $DBT_PROJECT_DIR"
        exit 1
    fi

    log "DBT project found at: $DBT_PROJECT_DIR"

    # Check project structure
    for dir in models macros tests; do
        if [ -d "$DBT_PROJECT_DIR/$dir" ]; then
            log "Found $dir directory"
        else
            warn "$dir directory not found"
        fi
    done
}

# Function to test DBT connection
test_dbt_connection() {
    log "Testing DBT connection..."

    cd "$DBT_PROJECT_DIR"

    # Run DBT debug
    if dbt debug --profiles-dir "$DBT_PROFILES_DIR" &> /dev/null; then
        log "DBT connection test successful"
        return 0
    else
        warn "DBT connection test failed"
        info "This might be expected during initial setup"

        # Show debug output for troubleshooting
        info "DBT debug output:"
        dbt debug --profiles-dir "$DBT_PROFILES_DIR" || true
        return 1
    fi
}

# Function to install DBT packages
install_dbt_packages() {
    log "Installing DBT packages..."

    cd "$DBT_PROJECT_DIR"

    if [ -f "packages.yml" ]; then
        log "Found packages.yml, installing dependencies..."
        dbt deps --profiles-dir "$DBT_PROFILES_DIR"
        log "DBT packages installed successfully"
    else
        info "No packages.yml found, skipping package installation"
    fi
}

# Function to create data directories for DuckDB
setup_data_directories() {
    if [ "$ENVIRONMENT" != "production" ]; then
        log "Setting up local data directories for development..."

        # Create data directories
        mkdir -p /opt/airflow/data/temp
        mkdir -p /opt/airflow/data/staging
        mkdir -p /opt/airflow/data/marts

        # Set proper permissions
        if [ "$(whoami)" = "root" ]; then
            chown -R airflow:airflow /opt/airflow/data
        fi

        chmod -R 755 /opt/airflow/data

        log "Local data directories created"
    fi
}

# Function to validate environment variables
validate_environment() {
    log "Validating environment configuration..."

    required_vars=("AIRFLOW_HOME" "DBT_PROFILES_DIR")

    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            error "Required environment variable $var is not set"
            exit 1
        else
            log "$var = ${!var}"
        fi
    done

    # Environment-specific validation
    if [ "$ENVIRONMENT" = "production" ]; then
        prod_vars=("AWS_DEFAULT_REGION")
        for var in "${prod_vars[@]}"; do
            if [ -z "${!var}" ]; then
                warn "Production environment variable $var is not set"
            else
                log "$var = ${!var}"
            fi
        done
    fi
}

# Function to run DBT compile test
test_dbt_compile() {
    log "Testing DBT compilation..."

    cd "$DBT_PROJECT_DIR"

    if dbt compile --profiles-dir "$DBT_PROFILES_DIR" &> /dev/null; then
        log "DBT compilation test successful"
        return 0
    else
        warn "DBT compilation test failed"
        info "DBT compile output:"
        dbt compile --profiles-dir "$DBT_PROFILES_DIR" || true
        return 1
    fi
}

# Main execution function
main() {
    log "Starting Catalunya Data Pipeline DBT Setup"
    log "Environment: $ENVIRONMENT"
    log "DBT Profiles Directory: $DBT_PROFILES_DIR"
    log "DBT Project Directory: $DBT_PROJECT_DIR"

    # Run setup steps
    validate_environment
    check_dbt_installation
    setup_profiles_directory
    setup_dbt_profiles
    validate_dbt_project
    setup_data_directories
    install_dbt_packages

    # Test the setup
    log "Running setup validation tests..."

    CONNECTION_OK=true
    COMPILE_OK=true

    if ! test_dbt_connection; then
        CONNECTION_OK=false
    fi

    if ! test_dbt_compile; then
        COMPILE_OK=false
    fi

    # Summary
    log "=== DBT Setup Summary ==="
    log "Environment: $ENVIRONMENT"
    log "DBT Connection: $([ "$CONNECTION_OK" = true ] && echo "✅ OK" || echo "⚠️  Warning")"
    log "DBT Compilation: $([ "$COMPILE_OK" = true ] && echo "✅ OK" || echo "⚠️  Warning")"

    if [ "$CONNECTION_OK" = true ] && [ "$COMPILE_OK" = true ]; then
        log "🎉 DBT setup completed successfully!"
        exit 0
    elif [ "$CONNECTION_OK" = true ] || [ "$COMPILE_OK" = true ]; then
        warn "DBT setup completed with warnings. Some tests failed but basic setup is working."
        exit 0
    else
        error "DBT setup failed. Please check the errors above."
        exit 1
    fi
}

# Help function
show_help() {
    echo "Catalunya Data Pipeline - DBT Setup Script"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help          Show this help message"
    echo "  -e, --env ENV       Set environment (development|production)"
    echo "  -p, --profiles DIR  Set DBT profiles directory"
    echo "  -d, --project DIR   Set DBT project directory"
    echo "  --test-only         Only run tests, skip setup"
    echo ""
    echo "Environment Variables:"
    echo "  ENVIRONMENT         Environment to setup (development|production)"
    echo "  DBT_PROFILES_DIR    DBT profiles directory"
    echo "  DBT_PROJECT_DIR     DBT project directory"
    echo ""
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -e|--env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -p|--profiles)
            DBT_PROFILES_DIR="$2"
            shift 2
            ;;
        -d|--project)
            DBT_PROJECT_DIR="$2"
            shift 2
            ;;
        --test-only)
            TEST_ONLY=true
            shift
            ;;
        *)
            error "Unknown option $1"
            show_help
            exit 1
            ;;
    esac
done

# Run main function or tests only
if [ "$TEST_ONLY" = true ]; then
    log "Running DBT tests only..."
    test_dbt_connection
    test_dbt_compile
else
    main
fi