#!/bin/bash

# Catalunya Data Pipeline - Attach Minimal IAM Permissions
# This script attaches minimal permissions needed for S3 infrastructure deployment

set -euo pipefail

echo "🔐 Attaching minimal IAM permissions for infrastructure testing..."

# --- Configuration ---
ENVIRONMENT=${1:-dev}
if [[ "$ENVIRONMENT" != "dev" && "$ENVIRONMENT" != "prod" ]]; then
    echo "❌ Invalid environment. Usage: $0 [dev|prod]"
    exit 1
fi
POLICY_NAME="CatalunyaDeploymentPolicy"
TMP_POLICY_FILE="/tmp/minimal-catalunyadeployment-policy.json"
GITHUB_REPO="vmchura/CloudGentGran"

# Get account ID for resource ARNs
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="eu-west-1"

# --- Function to create or update a GitHub OIDC role ---
create_github_role() {
    local role_name=$1

    echo "⏳ Handling GitHub OIDC role: $role_name"

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
}

# --- Cleanup on exit ---
trap "rm -f $TMP_POLICY_FILE" EXIT

# --- Create the minimal policy document ---
cat > "$TMP_POLICY_FILE" << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudFormationStackOps",
      "Effect": "Allow",
      "Action": [
        "cloudformation:CreateStack",
        "cloudformation:UpdateStack",
        "cloudformation:DeleteStack",
        "cloudformation:DescribeStacks",
        "cloudformation:GetTemplate",
        "cloudformation:CreateChangeSet",
        "cloudformation:ExecuteChangeSet",
        "cloudformation:DescribeChangeSet",
        "cloudformation:DescribeStackEvents",
        "cloudformation:GetTemplateSummary",
        "cloudformation:DescribeStackResources"
      ],
      "Resource": [
        "arn:aws:cloudformation:${REGION}:${ACCOUNT_ID}:stack/CatalunyaDataStack-${ENVIRONMENT}/*",
        "arn:aws:cloudformation:${REGION}:${ACCOUNT_ID}:stack/CDKToolkit/*"
      ]
    },
    {
      "Sid": "CloudFormationList",
      "Effect": "Allow",
      "Action": [
        "cloudformation:ListStacks"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "${REGION}"
        }
      }
    },
    {
      "Sid": "S3ProjectBuckets",
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:DeleteBucket",
        "s3:GetBucketLocation",
        "s3:GetBucketVersioning",
        "s3:GetBucketEncryption",
        "s3:GetBucketPublicAccessBlock",
        "s3:GetBucketNotification",
        "s3:GetBucketTagging",
        "s3:PutBucketVersioning",
        "s3:PutBucketEncryption",
        "s3:PutBucketPublicAccessBlock",
        "s3:PutBucketNotification",
        "s3:PutBucketTagging",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::catalunya-data-${ENVIRONMENT}",
        "arn:aws:s3:::catalunya-athena-results-${ENVIRONMENT}",
        "arn:aws:s3:::catalunya-catalog-${ENVIRONMENT}",
        "arn:aws:s3:::cdk-hnb659fds-*"
      ]
    },
    {
      "Sid": "S3ProjectObjects",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:GetObjectVersion",
        "s3:DeleteObjectVersion"
      ],
      "Resource": [
        "arn:aws:s3:::catalunya-data-${ENVIRONMENT}/*",
        "arn:aws:s3:::catalunya-athena-results-${ENVIRONMENT}/*",
        "arn:aws:s3:::catalunya-catalog-${ENVIRONMENT}/*",
        "arn:aws:s3:::cdk-hnb659fds-*/*"
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
        "arn:aws:iam::${ACCOUNT_ID}:role/cdk-*",
        "arn:aws:iam::${ACCOUNT_ID}:role/*S3AutoDeleteObjectsCustomResourceProviderRole*",
        "arn:aws:iam::${ACCOUNT_ID}:role/catalunya-*"
      ]
    },
    {
      "Sid": "LambdaProjectFunctions",
      "Effect": "Allow",
      "Action": [
        "lambda:CreateFunction",
        "lambda:DeleteFunction",
        "lambda:GetFunction",
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration",
        "lambda:InvokeFunction",
        "lambda:TagResource",
        "lambda:UntagResource",
        "lambda:ListTags",
        "lambda:AddPermission",
        "lambda:RemovePermission",
        "lambda:GetPolicy"
      ],
      "Resource": [
        "arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:*S3AutoDeleteObjectsCustomResourceProvider*",
        "arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:CatalunyaDataStack-${ENVIRONMENT}-*",
        "arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:catalunya-${ENVIRONMENT}-*"
      ]
    },
    {
      "Sid": "GlueDataCatalogMinimal",
      "Effect": "Allow",
      "Action": [
        "glue:CreateDatabase",
        "glue:DeleteDatabase",
        "glue:GetDatabase",
        "glue:UpdateDatabase",
        "glue:TagResource",
        "glue:UntagResource"
      ],
      "Resource": [
        "arn:aws:glue:${REGION}:${ACCOUNT_ID}:catalog",
        "arn:aws:glue:${REGION}:${ACCOUNT_ID}:database/catalunya_data_*"
      ]
    },
    {
      "Sid": "AthenaWorkgroupMinimal",
      "Effect": "Allow",
      "Action": [
        "athena:CreateWorkGroup",
        "athena:DeleteWorkGroup",
        "athena:GetWorkGroup",
        "athena:UpdateWorkGroup",
        "athena:TagResource",
        "athena:UntagResource"
      ],
      "Resource": [
        "arn:aws:athena:${REGION}:${ACCOUNT_ID}:workgroup/catalunya-workgroup-*"
      ]
    },
    {
      "Sid": "CDKBootstrapSSM",
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:GetParameters",
        "ssm:PutParameter",
        "ssm:DeleteParameter"
      ],
      "Resource": "arn:aws:ssm:${REGION}:${ACCOUNT_ID}:parameter/cdk-bootstrap*"
    },
    {
      "Sid": "IAMCDKRoleManagement",
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:GetRole",
        "iam:GetRolePolicy",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:TagRole",
        "iam:UntagRole"
      ],
      "Resource": "arn:aws:iam::${ACCOUNT_ID}:role/cdk-*"
    },
    {
      "Sid": "STSAssumeRole",
      "Effect": "Allow",
      "Action": [
        "sts:AssumeRole"
      ],
      "Resource": "arn:aws:iam::${ACCOUNT_ID}:role/cdk-*"
    },
    {
      "Sid": "ECRRepositoryManagement",
      "Effect": "Allow",
      "Action": [
        "ecr:DeleteRepository",
        "ecr:CreateRepository",
        "ecr:DescribeRepositories",
        "ecr:PutLifecyclePolicy",
        "ecr:SetRepositoryPolicy",
        "ecr:TagResource"
      ],
      "Resource": "arn:aws:ecr:${REGION}:${ACCOUNT_ID}:repository/cdk*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "${REGION}"
        }
      }
    },
    {
      "Sid": "AllowCDKBootstrapBucket",
      "Effect": "Allow",
      "Action": [
        "s3:GetBucketLocation",
        "s3:GetBucketVersioning",
        "s3:PutBucketVersioning",
        "s3:GetBucketEncryption",
        "s3:PutBucketEncryption",
        "s3:GetBucketPublicAccessBlock",
        "s3:PutBucketPublicAccessBlock"
      ],
      "Resource": "arn:aws:s3:::cdk-hnb659fds-*"
    },
    {
      "Sid": "AllowProjectTagging",
      "Effect": "Allow",
      "Action": [
        "tag:GetResources",
        "tag:TagResources",
        "tag:UntagResources"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "${REGION}"
        },
        "StringLike": {
          "aws:ResourceTag:Project": "CatalunyaDataPipeline"
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
create_github_role "catalunya-deployment-role-${ENVIRONMENT}"

echo "🚀 Starting minimal permissions setup..."


# Step 1: Create or update the policy
create_or_update_policy

# Step 2: Attach to roles
echo ""
echo "🔗 Attaching policy to GitHub deployment roles..."
attach_policy_to_role "catalunya-deployment-role-${ENVIRONMENT}"

echo ""
echo "✅ Minimal permissions setup complete!"
echo ""
echo "📋 Roles with attached policy:"
echo "  - catalunya-deployment-role-${ENVIRONMENT}"
