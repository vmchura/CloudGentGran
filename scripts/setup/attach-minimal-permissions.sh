#!/bin/bash

# Catalunya Data Pipeline - Attach Minimal IAM Permissions
# This script attaches minimal permissions needed for S3 infrastructure deployment

set -euo pipefail

echo "🔐 Attaching minimal IAM permissions for infrastructure testing..."

# --- Configuration ---
POLICY_NAME="CatalunyaDeploymentPolicy"
TMP_POLICY_FILE="/tmp/minimal-catalunyaeployment-policy.json"

# --- Cleanup on exit ---
trap "rm -f $TMP_POLICY_FILE" EXIT

# --- Create the minimal policy document ---
cat > "$TMP_POLICY_FILE" << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudFormationOps",
      "Effect": "Allow",
      "Action": [
        "cloudformation:CreateStack",
        "cloudformation:UpdateStack",
        "cloudformation:DeleteStack",
        "cloudformation:DescribeStacks",
        "cloudformation:GetTemplate"
      ],
      "Resource": "*"
    },
    {
      "Sid": "S3Buckets",
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:DeleteBucket",
        "s3:GetBucket*",
        "s3:PutBucket*",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::catalunya-data-*"
      ]
    },
    {
      "Sid": "S3Objects",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::catalunya-data-*/*"
      ]
    },
    {
      "Sid": "IAMPassRoles",
      "Effect": "Allow",
      "Action": [
        "iam:GetRole",
        "iam:PassRole"
      ],
      "Resource": [
        "arn:aws:iam::*:role/cdk-*",
        "arn:aws:iam::*:role/*S3AutoDeleteObjectsCustomResourceProviderRole*"
      ]
    },
    {
      "Sid": "LambdaS3Cleanup",
      "Effect": "Allow",
      "Action": [
        "lambda:CreateFunction",
        "lambda:DeleteFunction",
        "lambda:GetFunction",
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration",
        "lambda:InvokeFunction"
      ],
      "Resource": [
        "arn:aws:lambda:*:*:function:*S3AutoDeleteObjectsCustomResourceProvider*"
      ]
    },
    {
      "Sid": "CDKBootstrapSSM",
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:PutParameter"
      ],
      "Resource": "arn:aws:ssm:*:*:parameter/cdk-bootstrap/*"
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
            --description "Minimal permissions for Catalunya S3 infrastructure deployment" \
            --tags Key=Project,Value=CatalunyaDataPipeline \
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
        aws iam attach-role-policy \
            --role-name "$role_name" \
            --policy-arn "$policy_arn" \
            --no-cli-pager
        echo "✅ Policy attached to $role_name"
    else
        echo "⚠️  Role $role_name not found, skipping..."
    fi
}

# --- Main execution ---
echo "🚀 Starting minimal permissions setup..."

# Step 1: Create or update the policy
create_or_update_policy

# Step 2: Attach to roles

echo ""
echo "🔗 Attaching policy to GitHub deployment roles..."
attach_policy_to_role "catalunya-github-dbt-role-dev"

echo ""
echo "✅ Minimal permissions setup complete!"
echo ""
echo "📋 Roles with attached policy:"
echo "  - catalunya-github-dbt-role-dev (for develop branch deployments)"