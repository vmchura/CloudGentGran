FROM apache/airflow:2.8.0-python3.11

# Switch to root to install system dependencies
USER root

# Install system dependencies for DBT and AWS
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    vim \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and entrypoint script first (as root for permissions)
COPY requirements.txt /requirements.txt
COPY docker/entrypoint.sh /opt/airflow/custom_entrypoint.sh
RUN chmod +x /opt/airflow/custom_entrypoint.sh

# Switch back to airflow user for the rest
USER airflow

# Set up working directory
WORKDIR /opt/airflow

# Install Python dependencies
RUN pip install --user --upgrade pip
RUN pip install --user --no-cache-dir -r /requirements.txt

# Create necessary directories
RUN mkdir -p /opt/airflow/dags /opt/airflow/logs /opt/airflow/plugins
RUN mkdir -p /home/airflow/.dbt

# Copy configuration files
COPY dbt/profiles/ /opt/airflow/dbt_profiles/

# Set environment variables
ENV AIRFLOW_HOME=/opt/airflow
ENV AIRFLOW__CORE__LOAD_EXAMPLES=False
ENV AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=True
ENV AIRFLOW__WEBSERVER__EXPOSE_CONFIG=True
ENV DBT_PROFILES_DIR=/home/airflow/.dbt

# Expose Airflow webserver port
EXPOSE 8080

# Use the original Airflow entrypoint (but we'll call our script from docker-compose)
# No ENTRYPOINT override - use the default Airflow one