#!/bin/bash

# Local Development Testing with LocalStack
set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

LOCALSTACK_ENDPOINT="http://localhost:4566"

echo -e "${BLUE}🏗️ Local Development Testing with LocalStack${NC}"

# Function to check if LocalStack is running
check_localstack() {
    if curl -s $LOCALSTACK_ENDPOINT/_localstack/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ LocalStack is running${NC}"
        return 0
    else
        echo -e "${RED}❌ LocalStack is not running${NC}"
        echo "Start it with: cd localstack && docker-compose up -d"
        return 1
    fi
}

# Function to build Rust lambda locally
build_rust_lambda() {
    echo -e "${YELLOW}🦀 Building Rust lambda locally...${NC}"
    
    cd lambda/transformers/social_services
    # Build the lambda
    cargo lambda build --release --target x86_64-unknown-linux-gnu
    
    # Create deployment package
    mkdir -p deployment
    cp target/lambda/bootstrap/bootstrap deployment/
    cd deployment
    zip -r ../social-services-transformer.zip .
    cd ..
    
    # Create the expected artifact directory for CI/CD compatibility
    mkdir -p ../../../rust-lambda-build
    cp social-services-transformer.zip ../../../rust-lambda-build/
    cd ../../../rust-lambda-build
    unzip -o social-services-transformer.zip
    
    echo -e "${GREEN}✅ Rust lambda built and artifact prepared${NC}"
    cd ..
}

# Function to deploy to LocalStack
deploy_to_localstack() {
    echo -e "${YELLOW}🚀 Deploying to LocalStack...${NC}"
    
    cd infrastructure
    
    # Install dependencies
    npm install
    
    # Build TypeScript
    npm run build
    
    # Set environment to force use of pre-built artifacts
    export USE_PREBUILT_ARTIFACTS=true
    export CDK_LOCAL=true
    
    # Bootstrap CDK (if needed)
    npx cdklocal bootstrap --require-approval never || true
    
    # Deploy
    npx cdklocal deploy CatalunyaDataStack-dev \
        --require-approval never \
        --outputs-file cdk-outputs-localstack.json
    
    echo -e "${GREEN}✅ Deployed to LocalStack${NC}"
    
    cd ..
}

# Function to test the deployment
test_deployment() {
    echo -e "${YELLOW}🧪 Testing deployment...${NC}"
    
    export AWS_ACCESS_KEY_ID=test
    export AWS_SECRET_ACCESS_KEY=test
    export AWS_DEFAULT_REGION=eu-west-1
    
    echo "S3 Buckets:"
    aws --endpoint-url=$LOCALSTACK_ENDPOINT s3 ls
    
    echo ""
    echo "Lambda Functions:"
    aws --endpoint-url=$LOCALSTACK_ENDPOINT lambda list-functions \
        --query 'Functions[].FunctionName' --output table
    
    echo ""
    echo "EventBridge Rules:"
    aws --endpoint-url=$LOCALSTACK_ENDPOINT events list-rules \
        --query 'Rules[].Name' --output table
    
    echo -e "${GREEN}✅ Testing complete${NC}"
}

# Function to test lambda invocation
test_lambda_invocation() {
    echo -e "${YELLOW}🔥 Testing lambda invocation...${NC}"
    
    export AWS_ACCESS_KEY_ID=test
    export AWS_SECRET_ACCESS_KEY=test
    export AWS_DEFAULT_REGION=eu-west-1
    
    # Create test event
    cat > /tmp/test-event.json << EOF
{
  "detail": {
    "downloaded_date": "20250810",
    "bucket_name": "catalunya-data-dev-$(date +%s)",
    "semantic_identifier": "social_services"
  }
}
EOF

    # Get function name
    FUNCTION_NAME=$(aws --endpoint-url=$LOCALSTACK_ENDPOINT lambda list-functions \
        --query 'Functions[?contains(FunctionName, `social-services-transformer`)].FunctionName' \
        --output text)
    
    if [ -n "$FUNCTION_NAME" ]; then
        echo "Testing function: $FUNCTION_NAME"
        aws --endpoint-url=$LOCALSTACK_ENDPOINT lambda invoke \
            --function-name "$FUNCTION_NAME" \
            --payload file:///tmp/test-event.json \
            /tmp/response.json
        
        echo "Response:"
        cat /tmp/response.json | jq '.'
    else
        echo "No social-services-transformer function found"
    fi
    
    echo -e "${GREEN}✅ Lambda testing complete${NC}"
}

# Main execution
main() {
    if ! check_localstack; then
        exit 1
    fi
    
    build_rust_lambda
    deploy_to_localstack
    test_deployment
    test_lambda_invocation
    
    echo -e "${GREEN}🎉 LocalStack testing complete!${NC}"
    echo -e "${BLUE}💡 Tip: Check LocalStack logs with 'cd localstack && docker-compose logs -f'${NC}"
}

# Run if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
