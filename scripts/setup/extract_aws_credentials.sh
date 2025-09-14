#!/bin/bash

# Configuration
ENVIRONMENT=${1:-dev}
if [[ "$ENVIRONMENT" != "dev" && "$ENVIRONMENT" != "prod" ]]; then
    echo "❌ Invalid environment. Usage: $0 [dev|prod]"
    exit 1
fi

echo "🔄 Getting AWS credentials from CloudFormation..."

# Get AWS Account ID
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
echo "AWS_ACCOUNT: $AWS_ACCOUNT"

# Get stack outputs
ACCESS_KEY=$(aws cloudformation describe-stacks \
  --stack-name CatalunyaDataStack-$ENVIRONMENT \
  --query "Stacks[0].Outputs[?OutputKey=='AirflowAssumerAccessKeyId'].OutputValue" \
  --output text)
echo "ACCESS_KEY: $ACCESS_KEY"

SECRET_KEY=$(aws cloudformation describe-stacks \
  --stack-name CatalunyaDataStack-$ENVIRONMENT \
  --query "Stacks[0].Outputs[?OutputKey=='AirflowAssumerSecretAccessKey'].OutputValue" \
  --output text)
echo "SECRET_KEY: $SECRET_KEY"

EXTERNAL_ID=$(aws cloudformation describe-stacks \
  --stack-name CatalunyaDataStack-$ENVIRONMENT \
  --query "Stacks[0].Outputs[?OutputKey=='AirflowExternalId'].OutputValue" \
  --output text)
echo "EXTERNAL_ID: $EXTERNAL_ID"


cat <<EOF
  dokku run cloudgentgran-orchestration-$ENVIRONMENT \
  airflow connections add aws_cross_account_role  \
    --conn-type aws \
    --conn-login $ACCESS_KEY \
    --conn-password $SECRET_KEY \
    --conn-extra '{"region_name": "eu-west-1", "role_arn": "arn:aws:iam::$AWS_ACCOUNT:role/catalunya-airflow-cross-account-role-$ENVIRONMENT", "assume_role_kwargs": {"ExternalId": "$EXTERNAL_ID"}}'

  dokku config:set cloudgentgran-orchestration-$ENVIRONMENT \
    AWS_ACCESS_KEY_ID=$ACCESS_KEY \
    AWS_SECRET_ACCESS_KEY=$SECRET_KEY \
    AWS_DEFAULT_REGION=eu-west-1"
EOF

