# Create lambda


# Building Rust Lambda Functions

## AWS profile for MiniStack (one-time setup)

Commands below use the AWS profile `ministack`. Create it once:

```bash
# ~/.aws/credentials
[ministack]
aws_access_key_id = test
aws_secret_access_key = test

# ~/.aws/config
[profile ministack]
region = eu-west-1
output = json
```

Or skip profiles entirely and use env vars (`AWS_ACCESS_KEY_ID=test`,
`AWS_SECRET_ACCESS_KEY=test`, `AWS_DEFAULT_REGION=eu-west-1`) with
`--endpoint-url http://localhost:4566`.

```bash
cargo lambda new population_municipal_greater_65_mart
# Is this function an HTTP function? No (managed by apache airflow)
# Event type that this function receives: Empty
# Implement code
cargo lambda build --release --target x86_64-unknown-linux-gnu
cargo lambda deploy -p ministack --endpoint-url http://localhost:4566 --env-var BUCKET_NAME=catalunya-data-dev --env-var SEMANTIC_IDENTIFIER=municipal_population

cargo lambda deploy -p ministack --endpoint-url http://localhost:4566 --env-var BUCKET_NAME=catalunya-data-dev --env-var SEMANTIC_IDENTIFIER=social_services --env-var CATALOG_BUCKET_NAME=catalunya-catalog-dev --env-var ENVIRONMENT=local --binary-name social-services-transformer catalunya-dev-social-services-transformer


 cargo lambda invoke --remote -p ministack --endpoint-url http://localhost:4566 --data-ascii "{\"source_prefix\": \"landing/population_municipal_greater_65\" }" population_municipal_greater_65
 
cargo lambda invoke --remote -p ministack --endpoint-url http://localhost:4566 --data-ascii "{\"athena_database_name\": \"catalunya_data_dev\", \"bucket_name\": \"catalunya-data-dev\", \"downloaded_date\": \"20260127\", \"environment\": \"local\", \"semantic_identifier\": \"social_services\"}" catalunya-dev-social-services-transformer

 cargo lambda invoke --remote -p ministack --endpoint-url http://localhost:4566 --data-ascii "{\"source_prefix\": \"staging/population_municipal_greater_65/population_municipal_greater_65.parquet\" }" population_municipal_greater_65_mart

 aws --endpoint-url=http://localhost:4566 s3 cp s3://catalunya-data-dev/mart/population_municipal_greater_65/population_municipal_greater_65.parquet ./population_municipal_greater_65.parquet --profile ministack
```
## Validator

```bash
cd lambda/validators/social_services/

cargo lambda build --release --target x86_64-unknown-linux-gnu

aws --profile ministack     --endpoint-url=http://localhost:4566     lambda list-functions     --query 'Functions[].FunctionName'     --output table

cargo lambda deploy -p ministack --endpoint-url http://localhost:4566 --env-var BUCKET_NAME=catalunya-data-dev --env-var SEMANTIC_IDENTIFIER=social_services --env-var CATALOG_BUCKET_NAME=catalunya-catalog-dev --env-var ENVIRONMENT=local --binary-name social-services-validator catalunya-dev-social-services-validator


 cargo lambda invoke --remote -p ministack --endpoint-url http://localhost:4566 --data-ascii "{\"environment\": \"local\", \"downloaded_date\": \"20260225\" , \"bucket_name\": \"catalunya-data-dev\" , \"semantic_identifier\": \"social_services\"  }" catalunya-dev-social-services-validator
 
```



```bash
# Install cargo-lambda (one-time setup)
cargo install cargo-lambda

# Add the Lambda target architecture
rustup target add x86_64-unknown-linux-gnu
```


### Build Steps

1. **Navigate to the transformer directory**:
   ```bash
   cd ..
   # From project root
   cd lambda/transformers/social_services
   # 2. **Build the Lambda function**:
   # Build the lambda for production deployment
   cargo lambda build --release --target x86_64-unknown-linux-gnu
   # 3. **Prepare deployment artifacts**:
   
   # Return to project root
   cd ../../..
   
   # Create deployment directory
   mkdir -p rust-lambda-build
   
   # Copy the bootstrap binary to deployment directory
   cp lambda/transformers/social_services/target/lambda/bootstrap/bootstrap rust-lambda-build/
   cd rust-lambda-build
   zip social-services-transformer.zip bootstrap
   ```

### Alternative: build all lambdas at once

```bash
# Local build without Docker (fast iteration)
./scripts/test-act.sh --local-build
```
