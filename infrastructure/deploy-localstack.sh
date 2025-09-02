#!/bin/bash

# Deploy CDK Stack to LocalStack using cdklocal
set -e
set -o pipefail  # Ensure pipe failures are caught

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

LOCALSTACK_ENDPOINT="http://localhost:4566"

echo -e "${BLUE}🚀 Deploying CDK Stack to LocalStack using cdklocal${NC}"

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

# Set AWS credentials for LocalStack
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

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
