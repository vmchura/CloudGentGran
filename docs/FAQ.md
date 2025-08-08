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