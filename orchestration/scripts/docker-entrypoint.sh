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

# Set admin password from environment variable if provided
if [ -n "$AIRFLOW_ADMIN_PASSWORD" ]; then
    echo "Setting admin password from AIRFLOW_ADMIN_PASSWORD"
    echo "{\"admin\": \"$AIRFLOW_ADMIN_PASSWORD\"}" > /opt/airflow/simple_auth_manager_passwords.json.generated
fi

echo "=========================================="
echo "Starting Airflow"
echo "=========================================="

# Execute the original Airflow command
exec "$@"
