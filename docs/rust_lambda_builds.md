# Create lambda


# Building Rust Lambda Functions

```bash
cargo lambda new population_municipal_greater_65_mart
# Is this function an HTTP function? No (managed by apache airflow)
# Event type that this function receives: Empty
# Implement code
cargo lambda build --release --target x86_64-unknown-linux-gnu
cargo lambda deploy -p localstack --endpoint-url http://localhost:4566 --env-var BUCKET_NAME=catalunya-data-dev --env-var SEMANTIC_IDENTIFIER=population_municipal_greater_65

 cargo lambda invoke --remote -p localstack --endpoint-url http://localhost:4566 --data-ascii "{\"source_prefix\": \"landing/population_municipal_greater_65\" }" population_municipal_greater_65

 cargo lambda invoke --remote -p localstack --endpoint-url http://localhost:4566 --data-ascii "{\"source_prefix\": \"staging/population_municipal_greater_65/population_municipal_greater_65.parquet\" }" population_municipal_greater_65_mart

 aws --endpoint-url=http://localhost:4566 s3 cp s3://catalunya-data-dev/mart/population_municipal_greater_65/population_municipal_greater_65.parquet ./population_municipal_greater_65.parquet --profile localstack
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

