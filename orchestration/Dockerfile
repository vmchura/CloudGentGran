FROM apache/airflow:3.1.7-python3.13
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        git \
        postgresql-client \
        build-essential \
        unzip \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN node --version && npm --version

COPY --from=registry.k8s.io/git-sync/git-sync:v4.6.0 /git-sync /git-sync
RUN /git-sync --version

USER airflow

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Create all necessary directories first
RUN mkdir -p /opt/airflow/dags \
    && mkdir -p /opt/airflow/logs \
    && mkdir -p /opt/airflow/plugins \
    && mkdir -p /opt/airflow/config \
    && mkdir -p /opt/airflow/dbt \
    && mkdir -p /opt/airflow/scripts

# Copy git-sync scripts (dbt synced at runtime via git-sync)
COPY --chown=airflow:root scripts/ /opt/airflow/scripts/
RUN chmod +x /opt/airflow/scripts/*.sh

COPY --chown=airflow:root dags/ /opt/airflow/dags/
COPY --chown=airflow:root plugins/ /opt/airflow/plugins/
COPY --chown=airflow:root config/ /opt/airflow/config/

# Ensure plugins are importable
RUN find /opt/airflow/plugins -name "*.py" -exec chmod 644 {} \;

ENV DBT_PROJECT_DIR=/opt/airflow/dbt/mart
ENV DBT_PROFILES_DIR=/opt/airflow/dbt
ENV DATA_BUCKET=catalunya-data-dev
ENV CATALOG_BUCKET=catalunya-catalog-dev

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/api/v2/monitor/health || exit 1

EXPOSE 8080

CMD ["airflow", "standalone"]
