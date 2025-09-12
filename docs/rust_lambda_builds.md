# Building Rust Lambda Functions

This document provides instructions for building Rust-based AWS Lambda functions in the Catalunya Open Data Pipeline project.

## Overview

The Catalunya project includes Rust-based Lambda functions for high-performance data transformation tasks. Currently, the social services transformer is implemented in Rust for optimal performance when processing large datasets.

## Prerequisites

Before building Rust Lambda functions, ensure you have the following installed:

- **Rust toolchain**: Install from [rustup.rs](https://rustup.rs/)
- **cargo-lambda**: AWS Lambda deployment tool for Rust
- **Target architecture**: Linux GNU target for AWS Lambda

## One-time Setup

Run these commands once to set up your Rust environment for Lambda development:

```bash
# Install cargo-lambda (one-time setup)
cargo install cargo-lambda

# Add the Lambda target architecture
rustup target add x86_64-unknown-linux-gnu
```

## Building the Social Services Transformer

The social services transformer is located at `lambda/transformers/social_services/` and contains the Rust implementation for processing social services data.

### Build Steps

1. **Navigate to the transformer directory**:
   ```bash
   # From project root
   cd lambda/transformers/social_services
   ```

2. **Build the Lambda function**:
   ```bash
   # Build the lambda for production deployment
   cargo lambda build --release --target x86_64-unknown-linux-gnu
   ```

3. **Prepare deployment artifacts**:
   ```bash
   # Return to project root
   cd ../../..
   
   # Create deployment directory
   mkdir -p rust-lambda-build
   
   # Copy the bootstrap binary to deployment directory
   cp lambda/transformers/social_services/target/lambda/bootstrap/bootstrap rust-lambda-build/
   ```

### Build Output

After successful compilation, you'll find:

- **Binary location**: `lambda/transformers/social_services/target/lambda/bootstrap/bootstrap`
- **Deployment ready**: `rust-lambda-build/bootstrap`

The `bootstrap` file is the executable that AWS Lambda will run. It must be named exactly `bootstrap` for the custom runtime to work properly.

## Build Configuration

### Target Architecture

AWS Lambda requires the `x86_64-unknown-linux-gnu` target for compatibility with the Lambda execution environment.

### Optimization

The `--release` flag ensures the binary is optimized for production:
- Smaller binary size
- Better runtime performance
- Optimized memory usage

### Dependencies

The Rust Lambda functions use these key dependencies (as defined in `Cargo.toml`):
- `lambda_runtime`: AWS Lambda runtime for Rust
- `serde`: JSON serialization/deserialization
- `tokio`: Async runtime
- Additional crates specific to data processing needs

## Development Workflow

### Local Development

1. **Make code changes** in `lambda/transformers/social_services/src/`
2. **Test locally** (if applicable):
   ```bash
   cd lambda/transformers/social_services
   cargo test
   ```
3. **Build for Lambda**:
   ```bash
   cargo lambda build --release --target x86_64-unknown-linux-gnu
   ```
4. **Update deployment artifacts**:
   ```bash
   cd ../../..
   cp lambda/transformers/social_services/target/lambda/bootstrap/bootstrap rust-lambda-build/
   ```

### Integration with Infrastructure

The built Rust Lambda functions integrate with the CDK infrastructure:

1. **Infrastructure deployment** creates the Lambda function resource
2. **Code deployment** uploads the `bootstrap` binary from `rust-lambda-build/`
3. **Trigger configuration** sets up EventBridge rules for automatic execution

## Troubleshooting

### Common Build Issues

1. **Target not found**:
   ```
   Error: toolchain 'stable-x86_64-unknown-linux-gnu' is not available
   ```
   **Solution**: Run `rustup target add x86_64-unknown-linux-gnu`

2. **cargo-lambda not found**:
   ```
   Error: cargo-lambda command not found
   ```
   **Solution**: Install with `cargo install cargo-lambda`

3. **Permission denied on bootstrap**:
   ```
   Error: Permission denied when copying bootstrap
   ```
   **Solution**: Ensure the source file exists and you have write permissions to `rust-lambda-build/`

### Build Verification

To verify your build was successful:

```bash
# Check that the bootstrap file exists and is executable
ls -la rust-lambda-build/bootstrap

# Verify it's a Linux ELF binary
file rust-lambda-build/bootstrap
# Expected output: rust-lambda-build/bootstrap: ELF 64-bit LSB executable, x86-64...
```

### Performance Optimization

For optimal Lambda performance:

- Use `--release` builds for production
- Consider reducing binary size with link-time optimization
- Profile memory usage during development
- Test with representative dataset sizes

## Environment-Specific Builds

### Development Environment
- Build frequency: After each code change
- Optimization level: Release (for consistent testing)
- Target: Same as production for compatibility

### Production Environment
- Build frequency: During deployment pipeline
- Optimization level: Full release optimization
- Target: `x86_64-unknown-linux-gnu`
- Additional checks: Integration tests, performance benchmarks

## Integration with CI/CD

The Rust Lambda build process can be integrated into the GitHub Actions workflow:

```yaml
# Example GitHub Actions step (to be added to .github/workflows/)
- name: Build Rust Lambda
  run: |
    cd lambda/transformers/social_services
    cargo lambda build --release --target x86_64-unknown-linux-gnu
    cd ../../..
    mkdir -p rust-lambda-build
    cp lambda/transformers/social_services/target/lambda/bootstrap/bootstrap rust-lambda-build/
```

## Next Steps

- **Add more Rust transformers**: Follow the same pattern for additional data processing functions
- **Optimize build times**: Use cargo caching in CI/CD
- **Add integration tests**: Test the built Lambda functions with sample data
- **Monitor performance**: Set up CloudWatch metrics for runtime performance

## References

- [cargo-lambda documentation](https://cargo-lambda.info/)
- [AWS Lambda Rust runtime](https://github.com/awslabs/aws-lambda-rust-runtime)
- [Rust Lambda deployment guide](https://docs.aws.amazon.com/lambda/latest/dg/lambda-rust.html)