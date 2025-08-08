#!/bin/bash

# Deploy CDK Stack to LocalStack
set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

LOCALSTACK_ENDPOINT="http://localhost:4566"

echo -e "${BLUE}🚀 Deploying CDK Stack to LocalStack${NC}"

# Check if LocalStack is running
check_localstack() {
    if curl -s $LOCALSTACK_ENDPOINT/_localstack/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ LocalStack is running${NC}"
        return 0
    else
        echo -e "${RED}❌ LocalStack is not running${NC}"
        echo "Start it with: cd ../localstack && docker-compose up -d"
        return 1
    fi
}

if ! check_localstack; then
    exit 1
fi

# Set AWS environment for LocalStack
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=eu-west-1
export AWS_ENDPOINT_URL=$LOCALSTACK_ENDPOINT

# CDK environment
export CDK_DEFAULT_ACCOUNT=000000000000
export CDK_DEFAULT_REGION=eu-west-1

echo -e "${YELLOW}📦 Installing dependencies...${NC}"
npm install

echo -e "${YELLOW}🔨 Building CDK app...${NC}"
npm run build

echo -e "${YELLOW}📋 Bootstrapping CDK (if needed)...${NC}"
npx cdk bootstrap --app "node bin/infrastructure.js" || true

echo -e "${YELLOW}🚀 Deploying stack to LocalStack...${NC}"
npx cdk deploy CatalunyaDataStack-dev \
    --app "node bin/infrastructure.js" \
    --require-approval never \
    --outputs-file cdk-outputs.json

echo -e "${GREEN}✅ Deployment complete!${NC}"

echo -e "${BLUE}📊 Stack outputs:${NC}"
cat cdk-outputs.json | jq '.'

echo -e "${BLUE}📋 LocalStack Resources:${NC}"
echo "S3 Buckets:"
aws --endpoint-url=$LOCALSTACK_ENDPOINT s3 ls

echo "Lambda Functions:"
aws --endpoint-url=$LOCALSTACK_ENDPOINT lambda list-functions --query 'Functions[].FunctionName' --output table
