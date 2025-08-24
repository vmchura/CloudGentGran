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

# Copy DAGs and configuration
COPY --chown=airflow:root dags/ /opt/airflow/dags/
COPY --chown=airflow:root plugins/ /opt/airflow/plugins/
COPY --chown=airflow:root config/ /opt/airflow/config/

WORKDIR /opt/airflow
EXPOSE 8080

# Default command
CMD ["webserver"]