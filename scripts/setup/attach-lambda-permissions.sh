#!/bin/bash

# Catalunya Data Pipeline - Attach Lambda IAM Permissions
# This script attaches necessary permissions for Lambda functions to access S3 and write logs
# Usage: ./attach-lambda-permissions.sh [dev|prod]

set -euo pipefail

# --- Configuration ---
ENVIRONMENT=${1:-dev}
if [[ "$ENVIRONMENT" != "dev" && "$ENVIRONMENT" != "prod" ]]; then
    echo "❌ Invalid environment. Usage: $0 [dev|prod]"
    exit 1
fi

echo "🔐 Attaching Lambda IAM permissions for Catalunya Data Pipeline ($ENVIRONMENT)..."

POLICY_NAME="CatalunyaLambdaExtractorPolicy${ENVIRONMENT^}"
TMP_POLICY_FILE="/tmp/lambda-extractor-policy-${ENVIRONMENT}.json"

# Get account ID for resource ARNs
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="eu-west-1"

# --- Cleanup on exit ---
trap "rm -f $TMP_POLICY_FILE" EXIT

echo "Account ID: $ACCOUNT_ID"
echo "Region: $REGION"
echo "Environment: $ENVIRONMENT"
echo ""

# --- Create the Lambda policy document ---
cat > "$TMP_POLICY_FILE" << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudWatchLogGroups",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams"
      ],
      "Resource": [
        "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:/aws/lambda/catalunya-${ENVIRONMENT}-*",
        "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:/aws/lambda/catalunya-${ENVIRONMENT}-*:*"
      ]
    },
    {
      "Sid": "S3DataBucketRead",
      "Effect": "Allow",
      "Action": [
        "s3:GetBucketLocation",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::catalunya-data-${ENVIRONMENT}"
      ]
    },
    {
      "Sid": "S3DataBucketWrite",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl",
        "s3:GetObject",
        "s3:GetObjectVersion"
      ],
      "Resource": [
        "arn:aws:s3:::catalunya-data-${ENVIRONMENT}/landing/*"
      ]
    },
    {
      "Sid": "XRayPermissions",
      "Effect": "Allow",
      "Action": [
        "xray:PutTraceSegments",
        "xray:PutTelemetryRecords"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "${REGION}"
        }
      }
    }
  ]
}
EOF

# --- Create or update the IAM policy ---
create_or_update_policy() {
    echo "📋 Creating/updating policy: $POLICY_NAME"

    local account_id
    account_id=$(aws sts get-caller-identity --query Account --output text)
    local policy_arn="arn:aws:iam::${account_id}:policy/${POLICY_NAME}"

    if aws iam get-policy --policy-arn "$policy_arn" --no-cli-pager > /dev/null 2>&1; then
        echo "🔄 Policy exists, creating new version..."
        
        # Get current versions and delete old ones if we're at the limit
        local versions
        versions=$(aws iam list-policy-versions --policy-arn "$policy_arn" --query 'Versions[?!IsDefaultVersion]' --output json)
        local version_count
        version_count=$(echo "$versions" | jq length)
        
        # AWS allows max 5 versions, so delete oldest if we have 4 non-default versions
        if [[ $version_count -ge 4 ]]; then
            echo "🗑️  Deleting old policy versions..."
            local oldest_version
            oldest_version=$(echo "$versions" | jq -r 'sort_by(.CreateDate) | .[0].VersionId')
            aws iam delete-policy-version \
                --policy-arn "$policy_arn" \
                --version-id "$oldest_version" \
                --no-cli-pager
        fi
        
        aws iam create-policy-version \
            --policy-arn "$policy_arn" \
            --policy-document "file://$TMP_POLICY_FILE" \
            --set-as-default \
            --no-cli-pager
    else
        echo "🆕 Creating new policy..."
        aws iam create-policy \
            --policy-name "$POLICY_NAME" \
            --policy-document "file://$TMP_POLICY_FILE" \
            --description "Lambda extractor permissions for Catalunya Data Pipeline (${ENVIRONMENT})" \
            --tags Key=Project,Value=CatalunyaDataPipeline Key=Service,Value=Lambda \
            --no-cli-pager
    fi

    echo "✅ Policy $POLICY_NAME ready"
}

# --- Attach policy to a given role ---
attach_policy_to_role() {
    local role_name="$1"
    local account_id
    account_id=$(aws sts get-caller-identity --query Account --output text)
    local policy_arn="arn:aws:iam::${account_id}:policy/${POLICY_NAME}"

    echo "🔗 Attaching policy to role: $role_name"

    if aws iam get-role --role-name "$role_name" --no-cli-pager > /dev/null 2>&1; then
        # Check if policy is already attached
        if aws iam list-attached-role-policies --role-name "$role_name" --query "AttachedPolicies[?PolicyArn=='$policy_arn']" --output text | grep -q "$policy_arn"; then
            echo "ℹ️  Policy already attached to $role_name"
        else
            aws iam attach-role-policy \
                --role-name "$role_name" \
                --policy-arn "$policy_arn" \
                --no-cli-pager
            echo "✅ Policy attached to $role_name"
        fi
    else
        echo "⚠️  Role $role_name not found, skipping..."
    fi
}

# --- Main execution ---
echo "🚀 Starting Lambda permissions setup..."

# Step 1: Create or update the policy
create_or_update_policy

# Step 2: Attach to Lambda roles
echo ""
echo "🔗 Attaching policy to Lambda extractor role for $ENVIRONMENT..."
attach_policy_to_role "catalunya-lambda-extractor-role-${ENVIRONMENT}"

echo ""
echo "✅ Lambda permissions setup complete for $ENVIRONMENT!"
echo ""
echo "📋 Role with attached policy:"
echo "  - catalunya-lambda-extractor-role-${ENVIRONMENT}"
echo ""
echo "🔍 Policy grants the following permissions:"
echo "  - CloudWatch Logs: Create log groups and streams, write log events (${ENVIRONMENT} only)"
echo "  - S3: Read bucket metadata, write to landing/ prefix (${ENVIRONMENT} bucket only)"
echo "  - X-Ray: Put trace segments and telemetry records"
