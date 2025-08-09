1. Remove a policy:
```bash
aws iam list-policy-versions --policy-arn arn:aws:iam::<<ACCOUNT_ID>>:policy/CatalunyaDeploymentPolicy
aws iam delete-policy-version --policy-arn arn:aws:iam::<<ACCOUNT_ID>>:policy/CatalunyaDeploymentPolicy --version-id v5
aws iam delete-policy-version --policy-arn arn:aws:iam::<<ACCOUNT_ID>>:policy/CatalunyaDeploymentPolicy --version-id v6
```
2. Trigger a lambda

Json payload
```json
{
  "source": "eventbridge.schedule",
  "environment": "dev",
  "trigger_time": "2025-08-08T23:00:00Z",
  "version": "0",
  "id": "test-event-id",
  "detail-type": "Scheduled Event",
  "account": "123456789012",
  "time": "2025-08-08T23:00:00Z",
  "region": "eu-west-1",
  "resources": [
    "arn:aws:events:eu-west-1:<<ACCOUNT_ID>>:rule/catalunya-dev-api-extractor-schedule"
  ],
  "detail": {}
}
```

1. List all deployed Lambda functions:
`aws lambda list-functions --endpoint-url=http://localhost:4566`
2. Get specific Lambda function details:
`aws lambda get-function --function-name FUNCTION_NAME --endpoint-url=http://localhost:4566`
3. Invoke Lambda with empty payload:
`aws lambda invoke --function-name FUNCTION_NAME --endpoint-url=http://localhost:4566 --cli-binary-format raw-in-base64-out response.json`
4. Invoke Lambda with JSON payload:
`aws lambda invoke --function-name FUNCTION_NAME --endpoint-url=http://localhost:4566 --payload '{"key": "value"}' --cli-binary-format raw-in-base64-out response.json`
5. Invoke Lambda with file payload:
`aws lambda invoke --function-name FUNCTION_NAME --endpoint-url=http://localhost:4566 --payload file://path/to/event.json --cli-binary-format raw-in-base64-out response.json`
6. View response:
`cat response.json | jq .`
7. Check Lambda logs:`aws logs describe-log-groups --endpoint-url=http://localhost:4566`

# List log streams for a function
`aws logs describe-log-streams --log-group-name "/aws/lambda/FUNCTION_NAME" --endpoint-url=http://localhost:4566`

# Get recent log events
`aws logs get-log-events --log-group-name "/aws/lambda/FUNCTION_NAME" --log-stream-name "LOG_STREAM_NAME" --endpoint-url=http://localhost:4566`
S3 Testing Commands:
8. List S3 buckets:
`aws s3 ls --endpoint-url=http://localhost:4566`
9. List bucket contents:
`aws s3 ls s3://BUCKET_NAME --endpoint-url=http://localhost:4566 --recursive`
10. Download and view S3 file:
`aws s3 cp s3://BUCKET_NAME/path/to/file.json --endpoint-url=http://localhost:4566 - | head -n 20`
Complete Test Script Example:

```bash
#!/bin/bash

# Set environment variables
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

# Get function name (replace with your actual function name)
export FUNCTION_NAME="catalunya-dev-social_services"

# Test the function
echo "Testing Lambda function: $FUNCTION_NAME"
aws lambda invoke --function-name $FUNCTION_NAME --endpoint-url=http://localhost:4566 --payload '{}' --cli-binary-format raw-in-base64-out response.json

echo "Response"
cat response.json | jq .

# Check S3 if your function writes to S3
echo "Checking S3 contents:"
aws s3 ls s3://catalunya-data-dev --endpoint-url=http://localhost:4566 --recursive

# Clean up
rm response.json
```