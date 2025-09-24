# DBT Dockerfile for Catalunya Data Pipeline
# Updated for Athena/LocalStack integration

FROM python:3.11-slim

# Set environment variables
ENV DBT_PROJECT_DIR=/opt/dbt
ENV DBT_PROFILES_DIR=/home/dbt/.dbt
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    awscli \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create dbt user
RUN useradd -m -s /bin/bash dbt

# Install dbt with Athena adapter
RUN pip install --no-cache-dir \
    dbt-athena==1.9.5 \
    dbt-core==1.10.11 \
    pyathena[pandas]==3.18.0 \
    boto3==1.35.26 \
    botocore==1.35.26

# Create necessary directories
RUN mkdir -p /home/dbt/.dbt /opt/dbt

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