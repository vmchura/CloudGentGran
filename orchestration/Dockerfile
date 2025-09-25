FROM apache/airflow:3.0.6rc1-python3.12
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        git \
        postgresql-client \
        build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER airflow

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Create all necessary directories first
RUN mkdir -p /opt/airflow/dags \
    && mkdir -p /opt/airflow/logs \
    && mkdir -p /opt/airflow/plugins \
    && mkdir -p /opt/airflow/config \
    && mkdir -p /opt/airflow/dbt

COPY --chown=airflow:root dags/ /opt/airflow/dags/
COPY --chown=airflow:root plugins/ /opt/airflow/plugins/
COPY --chown=airflow:root config/ /opt/airflow/config/

COPY --chown=airflow:root dbt/ /opt/airflow/dbt/

RUN cp /opt/airflow/dbt/mart/profiles_template.yml /opt/airflow/dbt/profiles.yml

COPY --chown=airflow:root plugins/ /opt/airflow/plugins/
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