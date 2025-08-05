# AWS Credentials Setup for GitHub Actions

## Overview

This document describes how to configure GitHub repository secrets for AWS credentials to support the Catalunya Open Data Pipeline deployment across development and production environments.

## Required Secrets

The following GitHub secrets need to be configured for the project:

### Development Environment
- `AWS_ACCESS_KEY_ID_DEV` - AWS Access Key ID for development environment
- `AWS_SECRET_ACCESS_KEY_DEV` - AWS Secret Access Key for development environment
- `AWS_REGION_DEV` - AWS region for development environment (e.g., `eu-west-1`)

### Production Environment  
- `AWS_ACCESS_KEY_ID_PROD` - AWS Access Key ID for production environment
- `AWS_SECRET_ACCESS_KEY_PROD` - AWS Secret Access Key for production environment
- `AWS_REGION_PROD` - AWS region for production environment (e.g., `eu-west-1`)

## Prerequisites

Before setting up the secrets, ensure you have:

1. **AWS CLI configured** with appropriate profiles for dev/prod
2. **IAM users created** with the necessary permissions for:
   - S3 bucket management
   - Lambda function deployment
   - Athena access
   - EventBridge configuration
   - CDK deployment permissions
   - CloudWatch logging

## Required IAM Permissions

The AWS credentials should have the following permissions (minimum required):

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:*",
                "lambda:*",
                "athena:*",
                "events:*",
                "logs:*",
                "iam:*",
                "cloudformation:*",
                "cdk:*"
            ],
            "Resource": "*"
        }
    ]
}
```

## Setting Up Secrets

### Method 1: Using GitHub CLI (Recommended)

```bash
# Development Environment
gh secret set AWS_ACCESS_KEY_ID_DEV --body "YOUR_DEV_ACCESS_KEY_ID"
gh secret set AWS_SECRET_ACCESS_KEY_DEV --body "YOUR_DEV_SECRET_ACCESS_KEY"
gh secret set AWS_REGION_DEV --body "eu-west-1"

# Production Environment  
gh secret set AWS_ACCESS_KEY_ID_PROD --body "YOUR_PROD_ACCESS_KEY_ID"
gh secret set AWS_SECRET_ACCESS_KEY_PROD --body "YOUR_PROD_SECRET_ACCESS_KEY"
gh secret set AWS_REGION_PROD --body "eu-west-1"
```

### Method 2: Using GitHub Web Interface

1. Go to your repository on GitHub
2. Click on **Settings** tab
3. Navigate to **Security** > **Secrets and variables** > **Actions**
4. Click **New repository secret**
5. Add each secret one by one using the names listed above

## Usage in GitHub Actions

The secrets will be available in GitHub Actions workflows as environment variables:

```yaml
env:
  AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID_DEV }}
  AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY_DEV }}
  AWS_DEFAULT_REGION: ${{ secrets.AWS_REGION_DEV }}
```

## Security Best Practices

1. **Use separate AWS accounts** for development and production
2. **Implement least-privilege access** - only grant necessary permissions
3. **Rotate credentials regularly** - update secrets when credentials change
4. **Use IAM roles** when possible instead of long-term access keys
5. **Monitor access** using AWS CloudTrail
6. **Never commit credentials** to version control

## Environment-Specific Configuration

### Development Environment
- Region: `eu-west-1` (or your preferred EU region)
- S3 Bucket naming: `catalunya-data-dev`
- Resources tagged with `Environment: development`

### Production Environment
- Region: `eu-west-1` (or your preferred EU region)
- S3 Bucket naming: `catalunya-data-prod`  
- Resources tagged with `Environment: production`

## Verification

After setting up the secrets, you can verify they are configured correctly:

```bash
# List all configured secrets (names only, values are hidden)
gh secret list
```

The output should show all the AWS-related secrets listed above.

## Troubleshooting

### Common Issues

1. **Invalid credentials**: Verify the access key and secret key are correct
2. **Insufficient permissions**: Check that the IAM user has all required permissions
3. **Region mismatch**: Ensure the AWS region matches your intended deployment region
4. **Secret naming**: Verify secret names match exactly (case-sensitive)

### Testing Credentials

You can test the credentials locally before setting up secrets:

```bash
# Test development credentials
export AWS_ACCESS_KEY_ID="your_dev_access_key"
export AWS_SECRET_ACCESS_KEY="your_dev_secret_key"
export AWS_DEFAULT_REGION="eu-west-1"
aws sts get-caller-identity

# Test production credentials  
export AWS_ACCESS_KEY_ID="your_prod_access_key"
export AWS_SECRET_ACCESS_KEY="your_prod_secret_key"
export AWS_DEFAULT_REGION="eu-west-1"
aws sts get-caller-identity
```

## Next Steps

Once the AWS credentials are configured as GitHub secrets, you can proceed with:

1. **Phase 2**: Infrastructure as Code (AWS CDK) setup
2. **Phase 6**: GitHub Actions workflow configuration
3. **Phase 8**: Production deployment

The secrets will be automatically used by the GitHub Actions workflows to deploy and manage AWS resources across both development and production environments.
