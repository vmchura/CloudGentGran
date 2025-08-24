#!/usr/bin/env bash
set -euo pipefail

# Migrate DB
airflow db migrate

# Admin user setup
: "${AIRFLOW_ADMIN_USERNAME:=admin}"
: "${AIRFLOW_ADMIN_PASSWORD:?set AIRFLOW_ADMIN_PASSWORD in dokku config}"
: "${AIRFLOW_ADMIN_EMAIL:=admin@example.com}"
: "${AIRFLOW_ADMIN_FIRSTNAME:=Admin}"
: "${AIRFLOW_ADMIN_LASTNAME:=User}"

if ! airflow users list | awk '{print $1}' | grep -qx "$AIRFLOW_ADMIN_USERNAME"; then
  echo "Creating Airflow admin user '$AIRFLOW_ADMIN_USERNAME'"
  airflow users create \
    --username "$AIRFLOW_ADMIN_USERNAME" \
    --password "$AIRFLOW_ADMIN_PASSWORD" \
    --firstname "$AIRFLOW_ADMIN_FIRSTNAME" \
    --lastname "$AIRFLOW_ADMIN_LASTNAME" \
    --role Admin \
    --email "$AIRFLOW_ADMIN_EMAIL"
else
  echo "Admin user '$AIRFLOW_ADMIN_USERNAME' already exists"
fi

# Start services
airflow api-server --host 0.0.0.0 --port ${PORT:-8080} --workers ${WEB_CONCURRENCY:-2} --daemon
exec airflow scheduler
