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
  dokku config:set $DOKKU_APP \
    AWS_ACCESS_KEY_ID=$ACCESS_KEY \
    AWS_SECRET_ACCESS_KEY=$SECRET_KEY \
    AWS_DEFAULT_REGION=eu-west-1 \
    AIRFLOW_CONN_AWS_CROSS_ACCOUNT_ROLE="aws://$ACCESS_KEY:$SECRET_KEY@/?__extra__=%7B%22region_name%22%3A+%22eu-west-1%22%2C+%22role_arn%22%3A+%22arn%3Aaws%3Aiam%3A%$AWS_ACCOUNT%3Arole%2Fcatalunya-airflow-cross-account-role-$ENVIRONMENT%22%2C+%22assume_role_kwargs%22%3A+%7B%22ExternalId%22%3A+%22$EXTERNAL_ID%22%7D%7D"
EOF

