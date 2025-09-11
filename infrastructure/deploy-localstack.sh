#!/bin/bash

# Deploy CDK Stack to LocalStack using cdklocal
set -e
set -o pipefail  # Ensure pipe failures are caught
export AWS_PAGER=""
# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

LOCALSTACK_ENDPOINT="http://localhost:4566"

# Set CDK and AWS environment variables for eu-west-1 and LocalStack
export CDK_DEFAULT_REGION=eu-west-1
export AWS_REGION=eu-west-1
export AWS_DEFAULT_REGION=eu-west-1
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test

# For CDK >= 2.177.0, we need to explicitly allow region environment variables
export AWS_ENVAR_ALLOWLIST=AWS_REGION,AWS_DEFAULT_REGION,CDK_DEFAULT_REGION

echo -e "${BLUE}🚀 Deploying CDK Stack to LocalStack using cdklocal${NC}"
echo -e "${BLUE}🌍 Target region: ${CDK_DEFAULT_REGION}${NC}"
echo -e "${BLUE}🔧 Environment variables:${NC}"
echo -e "${BLUE}   CDK_DEFAULT_REGION=${CDK_DEFAULT_REGION}${NC}"
echo -e "${BLUE}   AWS_REGION=${AWS_REGION}${NC}"
echo -e "${BLUE}   AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION}${NC}"
echo -e "${BLUE}   AWS_ENVAR_ALLOWLIST=${AWS_ENVAR_ALLOWLIST}${NC}"

# Function for error handling
handle_error() {
    echo -e "${RED}❌ Error occurred during deployment at line $1${NC}"
    echo -e "${YELLOW}📄 Last few lines of output:${NC}"
    exit 1
}

# Set up error trap
trap 'handle_error $LINENO' ERR

# Check if LocalStack is running
check_localstack() {
    echo -e "${BLUE}🔍 Checking LocalStack status...${NC}"
    if curl -s $LOCALSTACK_ENDPOINT/_localstack/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ LocalStack is running${NC}"
        # Show LocalStack status
        curl -s $LOCALSTACK_ENDPOINT/_localstack/health | jq '.' || echo "LocalStack health check passed"
        return 0
    else
        echo -e "${RED}❌ LocalStack is not running or not accessible${NC}"
        echo -e "${YELLOW}Make sure LocalStack is started with Docker Compose${NC}"
        return 1
    fi
}

if ! check_localstack; then
    exit 1
fi

echo -e "${YELLOW}🧹 Cleaning up previous deployment outputs...${NC}"
rm -f cdk-outputs.json

echo -e "${YELLOW}📦 Installing dependencies...${NC}"
if npm install; then
    echo -e "${GREEN}✅ Dependencies installed${NC}"
else
    echo -e "${RED}❌ Failed to install dependencies${NC}"
    exit 1
fi

echo -e "${YELLOW}🔨 Building CDK app...${NC}"
if npm run build; then
    echo -e "${GREEN}✅ CDK app built successfully${NC}"
else
    echo -e "${RED}❌ Failed to build CDK app${NC}"
    exit 1
fi

echo -e "${YELLOW}📋 Bootstrapping CDK with cdklocal (if needed)...${NC}"
if npx cdklocal bootstrap --app "node bin/infrastructure.js" 2>&1; then
    echo -e "${GREEN}✅ CDK bootstrap completed${NC}"
else
    echo -e "${YELLOW}⚠️  CDK bootstrap failed, continuing anyway (might be already bootstrapped)${NC}"
fi

echo -e "${YELLOW}🚀 Deploying stack to LocalStack with cdklocal...${NC}"
echo -e "${BLUE}📄 Deployment progress:${NC}"
if npx cdklocal deploy CatalunyaDataStack-dev \
    --app "node bin/infrastructure.js" \
    --require-approval never \
    --outputs-file cdk-outputs.json \
    --progress events \
    --verbose; then
    echo -e "${GREEN}✅ CDK deployment successful${NC}"
else
    echo -e "${RED}❌ CDK deployment failed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Deployment complete!${NC}"

# Show deployment outputs
if [ -f cdk-outputs.json ]; then
    echo -e "${BLUE}📊 Stack outputs:${NC}"
    if command -v jq &> /dev/null; then
        cat cdk-outputs.json | jq '.'
    else
        cat cdk-outputs.json
    fi
else
    echo -e "${YELLOW}⚠️  No CDK outputs file generated${NC}"
fi

echo -e "${BLUE}📋 Verifying deployed LocalStack resources:${NC}"

echo -e "${YELLOW}S3 Buckets:${NC}"
if aws --endpoint-url=$LOCALSTACK_ENDPOINT s3 ls 2>&1; then
    echo -e "${GREEN}✅ S3 buckets listed successfully${NC}"
else
    echo -e "${YELLOW}⚠️  Could not list S3 buckets${NC}"
fi

echo -e "${YELLOW}Lambda Functions:${NC}"
if aws --endpoint-url=$LOCALSTACK_ENDPOINT lambda list-functions --query 'Functions[].FunctionName' --output table 2>&1; then
    echo -e "${GREEN}✅ Lambda functions listed successfully${NC}"
else
    echo -e "${YELLOW}⚠️  Could not list Lambda functions${NC}"
fi

echo -e "${GREEN}🎉 LocalStack deployment verification complete!${NC}"

echo -e "${BLUE}🔐 Verifying IAM Roles and Permissions in LocalStack:${NC}"

echo -e "${YELLOW}IAM Roles:${NC}"
if aws --endpoint-url=$LOCALSTACK_ENDPOINT iam list-roles --query 'Roles[?contains(RoleName, `catalunya`)].{RoleName:RoleName,Description:Description}' --output table 2>&1; then
    echo -e "${GREEN}✅ IAM roles listed successfully${NC}"
else
    echo -e "${YELLOW}⚠️  Could not list IAM roles${NC}"
fi

echo -e "${YELLOW}IAM Managed Policies:${NC}"
if aws --endpoint-url=$LOCALSTACK_ENDPOINT iam list-policies --scope Local --query 'Policies[?contains(PolicyName, `Catalunya`)].{PolicyName:PolicyName,Description:Description}' --output table 2>&1; then
    echo -e "${GREEN}✅ IAM policies listed successfully${NC}"
else
    echo -e "${YELLOW}⚠️  Could not list IAM policies${NC}"
fi