#!/bin/bash

set -e

echo "=========================================="
echo "Airflow Container Starting"
echo "=========================================="
echo "Time: $(date)"
echo "=========================================="

# Run git-sync to fetch dbt, dags, plugins, config from repository
echo "Running git-sync to fetch content from repository..."
/opt/airflow/scripts/sync-repo.sh

echo "=========================================="
echo "Starting Airflow"
echo "=========================================="

# Execute the original Airflow command
exec "$@"
