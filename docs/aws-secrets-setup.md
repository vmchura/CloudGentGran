# AWS Authentication Setup for GitHub Actions

The following IAM roles must exist in your AWS account with OIDC trust relationships configured for GitHub Actions:

## Development Environment Role
- **Role Name**: `catalunya-deployment-role-dev`
- **Purpose**: Deploy and manage development environment resources
- **Trusted Entity**: GitHub Actions from `develop` branch
- **Trust Policy**: OIDC provider for `token.actions.githubusercontent.com`

## Production Environment Role  
- **Role Name**: `catalunya-deployment-role-prod`
- **Purpose**: Deploy and manage production environment resources
- **Trusted Entity**: GitHub Actions from `main` branch only
- **Trust Policy**: OIDC provider for `token.actions.githubusercontent.com`

# 🛠️ Setting Up OIDC Authentication


## Step 1: Create IAM Roles

The roles were created automatically when you run the setup script:

```bash
# Run the role creation script
chmod +x scripts/setup/create-iam-roles.sh
./scripts/setup/create-iam-roles.sh
```


### Step 2: Configure GitHub Secret

```bash
# Set the AWS Account ID
gh secret set AWS_ACCOUNT_ID --body "123456789012"
```
