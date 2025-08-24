FROM apache/airflow:3.0.6rc1-python3.12

# Switch to root for installations
USER root

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Switch back to airflow user
USER airflow

# Copy and install requirements
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Create all necessary directories first
RUN mkdir -p /opt/airflow/dags \
    && mkdir -p /opt/airflow/logs \
    && mkdir -p /opt/airflow/plugins \
    && mkdir -p /opt/airflow/config \
    && mkdir -p /opt/airflow/dbt_mart

# Copy application files
COPY --chown=airflow:root dags/ /opt/airflow/dags/
COPY --chown=airflow:root plugins/ /opt/airflow/plugins/

# For now, create an empty dbt_mart directory
# Later we'll need to solve the DBT integration
RUN echo "# DBT project will be mounted here" > /opt/airflow/dbt_mart/README.md

WORKDIR /opt/airflow
EXPOSE 8080

# Default command
CMD ["webserver"]