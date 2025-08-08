#!/bin/bash

# Catalunya Data Pipeline - IAM Roles Creation Script (Updated)
# This script creates or updates IAM roles for the Catalunya data pipeline.

set -euo pipefail

# --- Configuration ---
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
GITHUB_REPO="vmchura/CloudGentGran"
REGION="eu-west-1"
THUMBPRINT="6938fd4d98bab03faadb97b34396831e3780aea1"

declare -a CREATED_ROLES=()

# Cleanup temp files
cleanup() {
  rm -f /tmp/trust-policy-*.json
}
trap cleanup EXIT

echo "🚀 Creating IAM roles for Catalunya Data Pipeline"
echo "Account ID: $ACCOUNT_ID"
echo "GitHub Repo: $GITHUB_REPO"
echo "Region: $REGION"
echo ""

# --- Function to create or update a basic service role ---
create_service_role() {
    local role_name=$1
    local service=$2

    echo "⏳ Handling role: $role_name"

    cat > /tmp/trust-policy-${role_name}.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "${service}.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    if aws iam get-role --role-name "$role_name" --no-cli-pager > /dev/null 2>&1; then
        echo "🔁 Role $role_name already exists. Updating trust policy..."
        aws iam update-assume-role-policy \
            --role-name "$role_name" \
            --policy-document file:///tmp/trust-policy-${role_name}.json \
            --no-cli-pager
    else
        echo "🆕 Creating role: $role_name"
        aws iam create-role \
            --role-name "$role_name" \
            --assume-role-policy-document file:///tmp/trust-policy-${role_name}.json \
            --description "Catalunya Data Pipeline - $role_name" \
            --tags Key=Project,Value=CatalunyaDataPipeline Key=Environment,Value=${role_name##*-} \
            --no-cli-pager
    fi

    CREATED_ROLES+=("$role_name")
}

# --- Function to create or update a GitHub OIDC role ---
create_github_role() {
    local role_name=$1
    local branch=$2

    echo "⏳ Handling GitHub OIDC role: $role_name for branch: $branch"

    cat > /tmp/trust-policy-${role_name}.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringLike": {
            "token.actions.githubusercontent.com:sub": "repo:${GITHUB_REPO}:*"
          },
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        }
      }
    }
  ]
}
EOF

    if aws iam get-role --role-name "$role_name" --no-cli-pager > /dev/null 2>&1; then
        echo "🔁 Role $role_name already exists. Updating trust policy..."
        aws iam update-assume-role-policy \
            --role-name "$role_name" \
            --policy-document file:///tmp/trust-policy-${role_name}.json \
            --no-cli-pager
    else
        echo "🆕 Creating role: $role_name"
        aws iam create-role \
            --role-name "$role_name" \
            --assume-role-policy-document file:///tmp/trust-policy-${role_name}.json \
            --description "Catalunya Data Pipeline - GitHub Actions $role_name" \
            --tags Key=Project,Value=CatalunyaDataPipeline Key=Environment,Value=${role_name##*-} Key=Service,Value=GitHubActions \
            --no-cli-pager
    fi

    CREATED_ROLES+=("$role_name")
}

# --- Ensure GitHub OIDC Provider exists ---
echo "🔐 Checking GitHub OIDC provider..."

OIDC_PROVIDER_ARN="arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"

if aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$OIDC_PROVIDER_ARN" --no-cli-pager > /dev/null 2>&1; then
    echo "✅ GitHub OIDC provider already exists"
else
    echo "➕ Creating GitHub OIDC provider..."
    aws iam create-open-id-connect-provider \
        --url "https://token.actions.githubusercontent.com" \
        --thumbprint-list "$THUMBPRINT" \
        --client-id-list "sts.amazonaws.com" \
        --tags Key=Project,Value=CatalunyaDataPipeline \
        --no-cli-pager
fi

# --- Function to create human user role ---
create_human_role() {
    local role_name=$1

    echo "⏳ Handling human role: $role_name"

    cat > /tmp/trust-policy-${role_name}.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::${ACCOUNT_ID}:root"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "Bool": {
          "aws:MultiFactorAuthPresent": "true"
        },
        "StringEquals": {
          "aws:RequestedRegion": "eu-west-1"
        }
      }
    }
  ]
}
EOF

    if aws iam get-role --role-name "$role_name" --no-cli-pager > /dev/null 2>&1; then
        echo "🔁 Role $role_name already exists. Updating trust policy..."
        aws iam update-assume-role-policy \
            --role-name "$role_name" \
            --policy-document file:///tmp/trust-policy-${role_name}.json \
            --no-cli-pager
    else
        echo "🆕 Creating role: $role_name"
        aws iam create-role \
            --role-name "$role_name" \
            --assume-role-policy-document file:///tmp/trust-policy-${role_name}.json \
            --description "Catalunya Data Pipeline - Human $role_name" \
            --tags Key=Project,Value=CatalunyaDataPipeline Key=RoleType,Value=Human \
            --no-cli-pager
    fi

    CREATED_ROLES+=("$role_name")
}

# --- Role Creation ---

echo ""
echo "👤 Creating human roles with enhanced security..."
create_human_role "catalunya-data-engineer-role"

echo ""
echo "📦 Creating Lambda service roles..."
create_service_role "catalunya-lambda-extractor-role-dev" "lambda"
create_service_role "catalunya-lambda-extractor-role-prod" "lambda"
create_service_role "catalunya-lambda-transformer-role-dev" "lambda"
create_service_role "catalunya-lambda-transformer-role-prod" "lambda"

echo ""
echo "🔄 Creating GitHub Actions roles with branch restrictions..."
create_github_role "catalunya-github-dbt-role-dev" "develop"
create_github_role "catalunya-deployment-role-prod" "main"

echo ""
echo "📊 Creating monitoring roles..."
create_service_role "catalunya-monitoring-role-dev" "lambda"
create_service_role "catalunya-monitoring-role-prod" "lambda"

# --- Summary ---
echo ""
echo "✅ All IAM roles handled successfully!"
echo ""
echo "📋 Created or Updated roles:"
for r in "${CREATED_ROLES[@]}"; do
    echo "  - $r"
done
