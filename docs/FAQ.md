1. Remove a policy:
```bash
aws iam list-policy-versions --policy-arn arn:aws:iam::<<ACCOUNT_ID>>:policy/CatalunyaDeploymentPolicy
aws iam delete-policy-version --policy-arn arn:aws:iam::<<ACCOUNT_ID>>:policy/CatalunyaDeploymentPolicy --version-id v5
aws iam delete-policy-version --policy-arn arn:aws:iam::<<ACCOUNT_ID>>:policy/CatalunyaDeploymentPolicy --version-id v6
```