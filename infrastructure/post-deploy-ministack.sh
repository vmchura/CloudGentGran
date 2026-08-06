#!/bin/bash

# Post-deploy resource creation for MiniStack.
# MiniStack CloudFormation does not support AWS::Athena::WorkGroup,
# AWS::Glue::Database or AWS::Glue::Table (see docs/ministack-migration.md,
# Entrada 9). The CFN resources are gated off with
# `-c createAnalyticsResources=false` and created here via the Athena/Glue
# APIs, which MiniStack does support.
set -e
set -o pipefail
export AWS_PAGER=""

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

ENDPOINT="http://localhost:4566"
REGION="eu-west-1"
DATABASE_NAME="catalunya_data_dev"
WORKGROUP_NAME="catalunya-workgroup-dev"
DATA_BUCKET="catalunya-data-dev"
CATALOG_BUCKET="catalunya-catalog-dev"
ATHENA_RESULTS_BUCKET="catalunya-athena-results-dev"

export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=$REGION

aws_cli() {
  aws --endpoint-url="$ENDPOINT" --region "$REGION" "$@"
}

echo -e "${BLUE}🏗️  Creating Athena/Glue resources via API (MiniStack CFN gap)...${NC}"

# ========================================
# Athena Workgroup
# ========================================
echo -e "${YELLOW}Creating Athena workgroup: ${WORKGROUP_NAME}${NC}"
if aws_cli athena create-work-group \
    --name "$WORKGROUP_NAME" \
    --description "Athena workgroup for Catalunya data pipeline - dev environment" \
    --configuration "ResultConfiguration={OutputLocation=s3://${ATHENA_RESULTS_BUCKET}/},EnforceWorkGroupConfiguration=false,PublishCloudWatchMetricsEnabled=true,BytesScannedCutoffPerQuery=1073741824,RequesterPaysEnabled=false" 2>&1; then
    echo -e "${GREEN}✅ Workgroup created${NC}"
else
    echo -e "${YELLOW}⚠️  Workgroup creation failed (may already exist)${NC}"
fi

# ========================================
# Glue Database
# ========================================
echo -e "${YELLOW}Creating Glue database: ${DATABASE_NAME}${NC}"
if aws_cli glue create-database --database-input "{
  \"Name\": \"${DATABASE_NAME}\",
  \"Description\": \"Catalunya data catalog for dev environment\",
  \"Parameters\": {
    \"classification\": \"parquet\",
    \"typeOfData\": \"file\",
    \"creator\": \"Catalunya Data Pipeline\",
    \"environment\": \"dev\"
  }
}" 2>&1; then
    echo -e "${GREEN}✅ Glue database created${NC}"
else
    echo -e "${YELLOW}⚠️  Glue database creation failed (may already exist)${NC}"
fi

# ========================================
# Glue Tables (mirror lib/glue-construct.ts)
# ========================================
PARQUET_FORMAT='"InputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat", "OutputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat", "SerdeInfo": {"SerializationLibrary": "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"}'

create_table() {
  local name="$1"
  local table_input="$2"
  echo -e "${YELLOW}Creating Glue table: ${name}${NC}"
  if aws_cli glue create-table --database-name "$DATABASE_NAME" --table-input "$table_input" 2>&1; then
      echo -e "${GREEN}✅ Table ${name} created${NC}"
  else
      echo -e "${YELLOW}⚠️  Table ${name} creation failed (may already exist)${NC}"
  fi
}

create_table "social_services" "{
  \"Name\": \"social_services\",
  \"TableType\": \"EXTERNAL_TABLE\",
  \"StorageDescriptor\": {
    \"Columns\": [
      {\"Name\": \"social_service_register_id\", \"Type\": \"string\"},
      {\"Name\": \"inscription_date\", \"Type\": \"date\"},
      {\"Name\": \"capacity\", \"Type\": \"int\"},
      {\"Name\": \"service_type_id\", \"Type\": \"string\"},
      {\"Name\": \"service_qualification_id\", \"Type\": \"string\"},
      {\"Name\": \"municipal_id\", \"Type\": \"string\"},
      {\"Name\": \"comarca_id\", \"Type\": \"string\"}
    ],
    \"Location\": \"s3://${DATA_BUCKET}/staging/social_services/\",
    ${PARQUET_FORMAT}
  },
  \"PartitionKeys\": [{\"Name\": \"downloaded_date\", \"Type\": \"string\"}]
}"

create_table "municipal_population" "{
  \"Name\": \"municipal_population\",
  \"TableType\": \"EXTERNAL_TABLE\",
  \"StorageDescriptor\": {
    \"Columns\": [
      {\"Name\": \"municipal_id\", \"Type\": \"string\"},
      {\"Name\": \"population_age_65_and_over\", \"Type\": \"int\"},
      {\"Name\": \"population\", \"Type\": \"int\"},
      {\"Name\": \"year\", \"Type\": \"int\"}
    ],
    \"Location\": \"s3://${DATA_BUCKET}/marts/municipal_population/\",
    ${PARQUET_FORMAT}
  }
}"

create_table "municipals" "{
  \"Name\": \"municipals\",
  \"TableType\": \"EXTERNAL_TABLE\",
  \"StorageDescriptor\": {
    \"Columns\": [
      {\"Name\": \"municipal_id\", \"Type\": \"string\"},
      {\"Name\": \"municipal_name\", \"Type\": \"string\"},
      {\"Name\": \"comarca_id\", \"Type\": \"string\"},
      {\"Name\": \"comarca_name\", \"Type\": \"string\"}
    ],
    \"Location\": \"s3://${CATALOG_BUCKET}/municipals/\",
    ${PARQUET_FORMAT}
  }
}"

create_table "service_type" "{
  \"Name\": \"service_type\",
  \"TableType\": \"EXTERNAL_TABLE\",
  \"StorageDescriptor\": {
    \"Columns\": [
      {\"Name\": \"service_type_id\", \"Type\": \"string\"},
      {\"Name\": \"service_type_description\", \"Type\": \"string\"},
      {\"Name\": \"created_at\", \"Type\": \"string\"}
    ],
    \"Location\": \"s3://${CATALOG_BUCKET}/service_type/\",
    ${PARQUET_FORMAT}
  }
}"

create_table "service_qualification" "{
  \"Name\": \"service_qualification\",
  \"TableType\": \"EXTERNAL_TABLE\",
  \"StorageDescriptor\": {
    \"Columns\": [
      {\"Name\": \"service_qualification_id\", \"Type\": \"string\"},
      {\"Name\": \"service_qualification_description\", \"Type\": \"string\"},
      {\"Name\": \"created_at\", \"Type\": \"string\"}
    ],
    \"Location\": \"s3://${CATALOG_BUCKET}/service_qualification/\",
    ${PARQUET_FORMAT}
  }
}"

echo -e "${GREEN}🎉 MiniStack post-deploy resources created${NC}"
