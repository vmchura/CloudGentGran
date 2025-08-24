#!/bin/bash

# Catalunya Data Pipeline - Setup Script
# This script only handles the initial setup, not Airflow execution

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Function to wait for database
wait_for_postgres() {
    log "Waiting for PostgreSQL to be ready..."
    while ! pg_isready -h postgres -U airflow; do
        sleep 1
    done
    log "PostgreSQL is ready!"
}

# Function to setup DBT profiles
setup_dbt_profiles() {
    log "Setting up DBT profiles..."

    # Create DBT profiles directory
    mkdir -p /home/airflow/.dbt

    # Determine environment and copy appropriate profile
    ENVIRONMENT=${ENVIRONMENT:-development}

    if [ "$ENVIRONMENT" = "production" ]; then
        log "Using production DBT profile (Athena)"
        cp /opt/airflow/dbt_profiles/profiles_prod.yml /home/airflow/.dbt/profiles.yml
    else
        log "Using development DBT profile (DuckDB)"
        cp /opt/airflow/dbt_profiles/profiles_dev.yml /home/airflow/.dbt/profiles.yml
    fi

    # Set proper permissions (check if we're root or airflow user)
    CURRENT_USER=$(whoami)
    if [ "$CURRENT_USER" = "root" ]; then
        chown -R airflow:root /home/airflow/.dbt
    else
        log "Running as $CURRENT_USER, skipping chown operations"
    fi

    log "DBT profiles setup complete"
}

# Function to initialize Airflow database
init_airflow_db() {
    if [ "$_AIRFLOW_DB_UPGRADE" = "true" ]; then
        log "Upgrading Airflow database..."
        airflow db upgrade
    fi

    if [ "$_AIRFLOW_WWW_USER_CREATE" = "true" ]; then
        log "Creating Airflow admin user..."
        airflow users create \
            --username ${_AIRFLOW_WWW_USER_USERNAME:-airflow} \
            --firstname Airflow \
            --lastname Admin \
            --role Admin \
            --email admin@catalunya-data.org \
            --password ${_AIRFLOW_WWW_USER_PASSWORD:-airflow}
    fi
}

# Function to validate DBT setup
validate_dbt_setup() {
    log "Validating DBT setup..."

    # Check if DBT is installed
    if ! command -v dbt &> /dev/null; then
        error "DBT is not installed!"
        exit 1
    fi

    # Check DBT version
    DBT_VERSION=$(dbt --version | head -1 | grep -o '[0-9]\+\.[0-9]\+\.[0-9]\+')
    log "DBT version: $DBT_VERSION"

    # Validate profiles
    if [ -f "/home/airflow/.dbt/profiles.yml" ]; then
        log "DBT profiles.yml found"
        # Test DBT connection (only in development)
        if [ "$ENVIRONMENT" = "development" ]; then
            log "Testing DBT connection..."
            cd /opt/airflow/dbt_mart
            if dbt debug --profiles-dir /home/airflow/.dbt 2>/dev/null; then
                log "DBT connection test successful"
            else
                warn "DBT connection test failed (this may be expected in initialization)"
            fi
        fi
    else
        error "DBT profiles.yml not found!"
        exit 1
    fi
}

# Function to setup directories
setup_directories() {
    log "Setting up directories..."

    # Create necessary directories with proper permissions
    mkdir -p /opt/airflow/logs
    mkdir -p /opt/airflow/dags
    mkdir -p /opt/airflow/plugins
    mkdir -p /opt/airflow/data

    # Set permissions
        chown -R airflow:root /opt/airflow/logs
        chown -R airflow:root /opt/airflow/data

    log "Directories setup complete"
}

# Main execution
main() {
    log "Starting Catalunya Data Pipeline Orchestration..."
    log "Environment: ${ENVIRONMENT:-development}"
    log "Airflow Home: ${AIRFLOW_HOME:-/opt/airflow}"

    # Setup directories
    setup_directories

    # Setup DBT profiles
    setup_dbt_profiles

    # If we're initializing, handle database setup
    if [ "$1" = "webserver" ] || [ "$1" = "scheduler" ]; then
        wait_for_postgres
    fi

    if [ "$_AIRFLOW_DB_UPGRADE" = "true" ] || [ "$_AIRFLOW_WWW_USER_CREATE" = "true" ]; then
        init_airflow_db
    fi

    # Validate DBT setup
    validate_dbt_setup

    log "Initialization complete. Starting Airflow command: $*"

    # Execute the original Airflow command
    exec airflow "$@"
}

# Run main function with all arguments
main "$@"