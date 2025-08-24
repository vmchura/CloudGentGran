#!/bin/bash

# Deploy CDK Stack to LocalStack using cdklocal
set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

LOCALSTACK_ENDPOINT="http://localhost:4566"

echo -e "${BLUE}🚀 Deploying CDK Stack to LocalStack using cdklocal${NC}"

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

echo -e "${YELLOW}📦 Installing dependencies...${NC}"
npm install

echo -e "${YELLOW}🔨 Building CDK app...${NC}"
npm run build

echo -e "${YELLOW}📋 Bootstrapping CDK with cdklocal (if needed)...${NC}"
npx cdklocal bootstrap --app "node bin/infrastructure.js" || true

echo -e "${YELLOW}🚀 Deploying stack to LocalStack with cdklocal...${NC}"
npx cdklocal deploy CatalunyaDataStack-dev \
    --app "node bin/infrastructure.js" \
    --require-approval never \
    --outputs-file cdk-outputs.json

echo -e "${GREEN}✅ Deployment complete!${NC}"

echo -e "${BLUE}📊 Stack outputs:${NC}"
cat cdk-outputs.json | jq '.'

export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

echo -e "${BLUE}📋 LocalStack Resources:${NC}"
echo "S3 Buckets:"
aws --endpoint-url=$LOCALSTACK_ENDPOINT s3 ls

echo "Lambda Functions:"
aws lambda list-functions --profile localstack --endpoint-url=http://localhost:4566 --query 'Functions[].FunctionName' --output table
