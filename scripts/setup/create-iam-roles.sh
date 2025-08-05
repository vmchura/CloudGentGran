#!/bin/bash

# Catalunya Data Pipeline - IAM Roles Creation Script
# This script creates all service account roles for the data pipeline
# Permissions will be attached separately

set -e

# Configuration
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
GITHUB_REPO="vmchura/CloudGentGran"
REGION="eu-west-1"

echo "🚀 Creating IAM roles for Catalunya Data Pipeline"
echo "Account ID: $ACCOUNT_ID"
echo "GitHub Repo: $GITHUB_REPO"
echo "Region: $REGION"
echo ""

# Function to create basic service role
create_service_role() {
    local role_name=$1
    local service=$2
    
    echo "Creating role: $role_name"
    
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

    if aws iam get-role --role-name "$role_name" --no-cli-pager 2>/dev/null; then
      echo "Role $role_name already exists. Skipping creation."
    else
        aws iam create-role \
            --role-name "$role_name" \
            --assume-role-policy-document file:///tmp/trust-policy-${role_name}.json \
            --description "Catalunya Data Pipeline - $role_name" \
            --tags Key=Project,Value=CatalunyaDataPipeline Key=Environment,Value=${role_name##*-} \
            --no-cli-pager
    fi


    rm /tmp/trust-policy-${role_name}.json
}

# Function to create GitHub Actions OIDC role
create_github_role() {
    local role_name=$1
    local branch=$2
    
    echo "Creating GitHub Actions role: $role_name"
    
    cat > /tmp/trust-policy-${role_name}.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Federated": "arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
            },
            "Action": "sts:AssumeRole",
            "Condition": {
                "StringEquals": {
                    "token.actions.githubusercontent.com:sub": "repo:${GITHUB_REPO}:ref:refs/heads/${branch}",
                    "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
                }
            }
        }
    ]
}
EOF

    aws iam create-role \
        --role-name "$role_name" \
        --assume-role-policy-document file:///tmp/trust-policy-${role_name}.json \
        --description "Catalunya Data Pipeline - GitHub Actions $role_name" \
        --tags Key=Project,Value=CatalunyaDataPipeline Key=Environment,Value=${role_name##*-} Key=Service,Value=GitHubActions \
        --no-cli-pager || echo "Role $role_name already exists"
    
    rm /tmp/trust-policy-${role_name}.json
}

# Check if GitHub OIDC provider exists, create if not
echo "🔐 Checking GitHub OIDC provider..."
aws iam get-open-id-connect-provider \
    --open-id-connect-provider-arn "arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com" \
    --no-cli-pager 2>/dev/null || {
    echo "Creating GitHub OIDC provider..."
    aws iam create-open-id-connect-provider \
        --url "https://token.actions.githubusercontent.com" \
        --thumbprint-list "6938fd4d98bab03faadb97b34396831e3780aea1" \
        --client-id-list "sts.amazonaws.com" \
        --tags Key=Project,Value=CatalunyaDataPipeline \
        --no-cli-pager
}

echo ""
echo "📦 Creating Lambda service roles..."

# Lambda Extractor Roles
create_service_role "catalunya-lambda-extractor-role-dev" "lambda"
create_service_role "catalunya-lambda-extractor-role-prod" "lambda"

# Lambda Transformer Roles  
create_service_role "catalunya-lambda-transformer-role-dev" "lambda"
create_service_role "catalunya-lambda-transformer-role-prod" "lambda"

echo ""
echo "🔄 Creating GitHub Actions roles..."

# GitHub Actions DBT Roles
create_github_role "catalunya-github-dbt-role-dev" "develop"
create_github_role "catalunya-github-dbt-role-prod" "main"

echo ""
echo "🚀 Creating deployment role..."

# Production Deployment Role (only prod)
create_github_role "catalunya-deployment-role-prod" "main"

echo ""
echo "📊 Creating monitoring roles..."

# Monitoring Roles
create_service_role "catalunya-monitoring-role-dev" "lambda"
create_service_role "catalunya-monitoring-role-prod" "lambda"

echo ""
echo "✅ All IAM roles created successfully!"
echo ""
echo "📋 Created roles:"
echo "  Lambda Extractor: catalunya-lambda-extractor-role-{dev,prod}"
echo "  Lambda Transformer: catalunya-lambda-transformer-role-{dev,prod}"
echo "  GitHub Actions DBT: catalunya-github-dbt-role-{dev,prod}"
echo "  Production Deployment: catalunya-deployment-role-prod"
echo "  Monitoring: catalunya-monitoring-role-{dev,prod}"
echo ""
echo "🔧 Next steps:"
echo "  1. Attach appropriate policies to each role"
echo "  2. Test OIDC authentication with GitHub Actions"
echo "  3. Update CDK code to use these roles"
echo ""
