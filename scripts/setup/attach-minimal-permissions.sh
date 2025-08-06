#!/bin/bash

# Catalunya Data Pipeline - Attach Minimal IAM Permissions
# This script attaches minimal permissions needed for S3 infrastructure deployment

set -euo pipefail

echo "🔐 Attaching minimal IAM permissions for S3 infrastructure testing..."

# --- Configuration ---
POLICY_NAME="CatalunyaS3DeploymentPolicy"

# --- Create the minimal policy document ---
cat > /tmp/minimal-s3-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudFormationOperations",
      "Effect": "Allow",
      "Action": [
        "cloudformation:CreateStack",
        "cloudformation:UpdateStack",
        "cloudformation:DeleteStack",
        "cloudformation:DescribeStacks",
        "cloudformation:DescribeStackEvents",
        "cloudformation:DescribeStackResources",
        "cloudformation:GetTemplate",
        "cloudformation:ListStackResources",
        "cloudformation:ValidateTemplate"
      ],
      "Resource": "*"
    },
    {
      "Sid": "S3BucketOperations",
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:DeleteBucket",
        "s3:GetBucketLocation",
        "s3:GetBucketPolicy",
        "s3:PutBucketPolicy",
        "s3:DeleteBucketPolicy",
        "s3:GetBucketTagging",
        "s3:PutBucketTagging",
        "s3:GetLifecycleConfiguration",
        "s3:PutLifecycleConfiguration",
        "s3:GetBucketCors",
        "s3:PutBucketCors",
        "s3:GetBucketVersioning",
        "s3:PutBucketVersioning",
        "s3:GetBucketPublicAccessBlock",
        "s3:PutBucketPublicAccessBlock"
      ],
      "Resource": [
        "arn:aws:s3:::catalunya-data-*"
      ]
    },
    {
      "Sid": "S3ObjectOperations",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::catalunya-data-*",
        "arn:aws:s3:::catalunya-data-*/*"
      ]
    },
    {
      "Sid": "IAMOperations",
      "Effect": "Allow",
      "Action": [
        "iam:GetRole",
        "iam:PassRole",
        "iam:CreateRole",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:DeleteRole",
        "iam:UpdateAssumeRolePolicy"
      ],
      "Resource": [
        "arn:aws:iam::*:role/cdk-*",
        "arn:aws:iam::*:role/*S3AutoDeleteObjectsCustomResourceProviderRole*"
      ]
    },
    {
      "Sid": "LambdaOperations", 
      "Effect": "Allow",
      "Action": [
        "lambda:CreateFunction",
        "lambda:DeleteFunction",
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration",
        "lambda:GetFunction",
        "lambda:InvokeFunction"
      ],
      "Resource": [
        "arn:aws:lambda:*:*:function:*S3AutoDeleteObjectsCustomResourceProvider*"
      ]
    },
    {
      "Sid": "CDKBootstrapOperations",
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:PutParameter"
      ],
      "Resource": [
        "arn:aws:ssm:*:*:parameter/cdk-bootstrap/*"
      ]
    }
  ]
}
EOF

# --- Function to create policy ---
create_policy() {
    echo "📋 Creating/updating policy: $POLICY_NAME"
    
    local account_id=$(aws sts get-caller-identity --query Account --output text)
    local policy_arn="arn:aws:iam::${account_id}:policy/${POLICY_NAME}"
    
    if aws iam get-policy --policy-arn "$policy_arn" --no-cli-pager > /dev/null 2>&1; then
        echo "🔄 Policy exists, creating new version..."
        aws iam create-policy-version \
            --policy-arn "$policy_arn" \
            --policy-document file:///tmp/minimal-s3-policy.json \
            --set-as-default \
            --no-cli-pager
    else
        echo "🆕 Creating new policy..."
        aws iam create-policy \
            --policy-name "$POLICY_NAME" \
            --policy-document file:///tmp/minimal-s3-policy.json \
            --description "Minimal permissions for Catalunya S3 infrastructure deployment" \
            --tags Key=Project,Value=CatalunyaDataPipeline \
            --no-cli-pager
    fi
    
    echo "✅ Policy $POLICY_NAME ready"
    return 0
}

# --- Function to attach policy to role ---
attach_policy_to_role() {
    local role_name=$1
    local account_id=$(aws sts get-caller-identity --query Account --output text)
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
echo "Starting minimal permissions setup..."
echo ""

# Create the policy
create_policy

echo ""
echo "🔗 Attaching policy to GitHub roles..."

# Attach to GitHub roles
attach_policy_to_role "catalunya-github-dbt-role-dev"

echo ""
echo "✅ Minimal permissions setup complete!"
echo ""
echo "📋 Roles with attached policy:"
echo "  - catalunya-github-dbt-role-dev (for develop branch deployments)"
echo "  - catalunya-deployment-role-prod (for main branch deployments)"
echo ""
echo "🚀 You can now test deployments:"
echo "  - Push to develop branch → deploys to development" 
echo "  - Push to main branch → deploys to production"

# Cleanup
rm -f /tmp/minimal-s3-policy.json
