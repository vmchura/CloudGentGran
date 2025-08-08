#!/bin/bash

# LocalStack Setup Script for CloudGentGran
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

LOCALSTACK_ENDPOINT="http://localhost:4566"

echo -e "${BLUE}🚀 Setting up LocalStack for CloudGentGran${NC}"

# Check if LocalStack is running
check_localstack() {
    if curl -s $LOCALSTACK_ENDPOINT/health > /dev/null; then
        echo -e "${GREEN}✅ LocalStack is running${NC}"
        return 0
    else
        echo -e "${RED}❌ LocalStack is not running${NC}"
        echo "Start it with: docker-compose up -d"
        return 1
    fi
}

# Create S3 buckets
create_s3_buckets() {
    echo -e "${YELLOW}📦 Creating S3 buckets...${NC}"
    
    # Landing bucket
    aws --endpoint-url=$LOCALSTACK_ENDPOINT s3 mb s3://cloudgentgran-landing-dev
    aws --endpoint-url=$LOCALSTACK_ENDPOINT s3 mb s3://cloudgentgran-landing-prod
    
    # Processed bucket
    aws --endpoint-url=$LOCALSTACK_ENDPOINT s3 mb s3://cloudgentgran-processed-dev
    aws --endpoint-url=$LOCALSTACK_ENDPOINT s3 mb s3://cloudgentgran-processed-prod
    
    # Test bucket
    aws --endpoint-url=$LOCALSTACK_ENDPOINT s3 mb s3://test-bucket-local
    
    echo -e "${GREEN}✅ S3 buckets created${NC}"
}

# List created resources
list_resources() {
    echo -e "${YELLOW}📋 LocalStack Resources:${NC}"
    
    echo -e "${BLUE}S3 Buckets:${NC}"
    aws --endpoint-url=$LOCALSTACK_ENDPOINT s3 ls
    
    echo -e "${BLUE}Lambda Functions:${NC}"
    aws --endpoint-url=$LOCALSTACK_ENDPOINT lambda list-functions --query 'Functions[].FunctionName' --output table
}

# Create IAM role for Lambda
create_iam_role() {
    echo -e "${YELLOW}👤 Creating IAM role...${NC}"
    
    # Create trust policy
    cat > /tmp/trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    # Create execution policy
    cat > /tmp/lambda-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": "*"
    }
  ]
}
EOF

    # Create role
    aws --endpoint-url=$LOCALSTACK_ENDPOINT iam create-role \
        --role-name lambda-execution-role \
        --assume-role-policy-document file:///tmp/trust-policy.json \
        --output table || true

    # Attach policy
    aws --endpoint-url=$LOCALSTACK_ENDPOINT iam put-role-policy \
        --role-name lambda-execution-role \
        --policy-name lambda-execution-policy \
        --policy-document file:///tmp/lambda-policy.json || true

    echo -e "${GREEN}✅ IAM role created${NC}"
}

# Deploy Lambda function
deploy_lambda() {
    echo -e "${YELLOW}🔧 Deploying Lambda function to LocalStack...${NC}"
    
    cd ../lambda/extractors/sam
    
    # Build SAM application
    sam build
    
    # Deploy to LocalStack
    sam deploy \
        --stack-name cloudgentgran-local \
        --s3-bucket cloudgentgran-landing-dev \
        --region us-east-1 \
        --no-confirm-changeset \
        --no-fail-on-empty-changeset \
        --parameter-overrides Environment=dev \
        --endpoint-url $LOCALSTACK_ENDPOINT
    
    cd - > /dev/null
    echo -e "${GREEN}✅ Lambda function deployed${NC}"
}

# Test Lambda function
test_lambda() {
    echo -e "${YELLOW}🧪 Testing Lambda function...${NC}"
    
    # Test with LocalStack
    aws --endpoint-url=$LOCALSTACK_ENDPOINT lambda invoke \
        --function-name cloudgentgran-local-ApiExtractorFunction \
        --payload '{"test": true, "source": "localstack"}' \
        /tmp/lambda-response.json
    
    echo -e "${BLUE}Lambda Response:${NC}"
    cat /tmp/lambda-response.json | jq '.'
    
    echo -e "${BLUE}S3 Objects:${NC}"
    aws --endpoint-url=$LOCALSTACK_ENDPOINT s3 ls s3://cloudgentgran-landing-dev --recursive
}

# Main execution
main() {
    if ! check_localstack; then
        exit 1
    fi
    
    create_s3_buckets
    create_iam_role
    # deploy_lambda  # Uncomment when you want to test deployment
    list_resources
    
    echo -e "${GREEN}🎉 LocalStack setup complete!${NC}"
    echo -e "${BLUE}Access LocalStack at: $LOCALSTACK_ENDPOINT${NC}"
    echo -e "${BLUE}LocalStack Web UI: $LOCALSTACK_ENDPOINT/_localstack/health${NC}"
}

# Set AWS credentials for LocalStack
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

case "${1:-setup}" in
    "setup")
        main
        ;;
    "buckets")
        check_localstack && create_s3_buckets
        ;;
    "lambda")
        check_localstack && deploy_lambda
        ;;
    "test")
        check_localstack && test_lambda
        ;;
    "list")
        check_localstack && list_resources
        ;;
    *)
        echo "Usage: $0 [setup|buckets|lambda|test|list]"
        ;;
esac
