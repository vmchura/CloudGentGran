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

# Switch back to airflow user
USER airflow

# Set up working directory
WORKDIR /opt/airflow

# Copy requirements and install Python dependencies
COPY requirements.txt /requirements.txt
RUN pip install --user --upgrade pip
RUN pip install --user --no-cache-dir -r /requirements.txt

# Create necessary directories
RUN mkdir -p /opt/airflow/dags /opt/airflow/logs /opt/airflow/plugins

# Copy DBT profiles
COPY dbt/profiles/ /opt/airflow/dbt_profiles/
RUN mkdir -p /home/airflow/.dbt

# Copy Airflow configuration
COPY config/ /opt/airflow/config/
COPY airflow/config/airflow.cfg /opt/airflow/airflow.cfg

# Copy entrypoint script
COPY docker/entrypoint.sh /opt/airflow/entrypoint.sh
RUN chmod +x /opt/airflow/entrypoint.sh

# Set environment variables
ENV AIRFLOW_HOME=/opt/airflow
ENV AIRFLOW__CORE__LOAD_EXAMPLES=False
ENV AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=True
ENV AIRFLOW__WEBSERVER__EXPOSE_CONFIG=True
ENV DBT_PROFILES_DIR=/home/airflow/.dbt

# Expose Airflow webserver port
EXPOSE 8080

# Use custom entrypoint
ENTRYPOINT ["/opt/airflow/entrypoint.sh"]