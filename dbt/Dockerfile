# DBT Dockerfile for Catalunya Data Pipeline

FROM python:3.11-slim

# Set environment variables
ENV DBT_PROJECT_DIR=/opt/dbt
ENV DBT_PROFILES_DIR=/home/dbt/.dbt
ENV PYTHONUNBUFFERED=1
ENV DBT_TARGET=standalone
# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    awscli \
    && rm -rf /var/lib/apt/lists/*

# Create dbt user
RUN useradd -m -s /bin/bash dbt

RUN pip install --no-cache-dir \
    dbt-duckdb==1.9.6 \
    dbt-core==1.10.11

# Create necessary directories
RUN mkdir -p /home/dbt/.dbt /opt/dbt/local_data

# Copy profiles template and rename to profiles.yml
COPY mart/profiles_template.yml /home/dbt/.dbt/profiles.yml

# Set ownership
RUN chown -R dbt:dbt /home/dbt /opt/dbt

# Switch to dbt user
USER dbt

# Set working directory to project
WORKDIR /opt/dbt

# Default command
CMD ["tail", "-f", "/dev/null"]