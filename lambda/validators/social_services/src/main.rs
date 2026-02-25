use anyhow::{anyhow, Result};
use aws_config::meta::region::RegionProviderChain;
use aws_sdk_s3::Client;
use chrono::Utc;
use jsonschema::{JSONSchema, ValidationError};
use lambda_runtime::{service_fn, Error, LambdaEvent};
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::io::Cursor;

const SCHEMA_JSON: &str = include_str!("social_services.v1.json");

#[derive(Deserialize, Serialize)]
struct LambdaInput {
    environment: String,
    downloaded_date: String,
    bucket_name: String,
    semantic_identifier: String,
}

#[derive(Serialize)]
struct LambdaOutput {
    #[serde(rename = "statusCode")]
    status_code: u16,
    success: bool,
    message: String,
    timestamp: String,
    processor: String,
    data: Option<ValidationResult>,
}

#[derive(Serialize)]
struct ValidationResult {
    source_prefix: String,
    files_validated: usize,
    records_validated: usize,
    records_passed: usize,
    records_failed: usize,
    validation_errors: Vec<RecordValidationError>,
}

#[derive(Serialize)]
struct RecordValidationError {
    file: String,
    record_index: usize,
    errors: Vec<String>,
}

#[tokio::main]
async fn main() -> Result<(), Error> {
    lambda_runtime::run(service_fn(function_handler)).await
}

async fn function_handler(event: LambdaEvent<LambdaInput>) -> Result<LambdaOutput, Error> {
    println!("Starting validation process at {}", Utc::now());
    println!("Received event: {}", serde_json::to_string(&event.payload)?);

    let region_provider = RegionProviderChain::default_provider().or_else("eu-west-1");
    let shared_config = aws_config::defaults(aws_config::BehaviorVersion::latest())
        .region(region_provider)
        .load()
        .await;
    let s3_client = Client::new(&shared_config);

    let downloaded_date = &event.payload.downloaded_date;
    let bucket_name = &event.payload.bucket_name;
    let semantic_identifier = &event.payload.semantic_identifier;

    println!(
        "Validating files: s3://{}/landing/{}/downloaded_date={}",
        bucket_name, semantic_identifier, downloaded_date
    );

    let source_prefix = format!(
        "landing/{}/downloaded_date={}/",
        semantic_identifier, downloaded_date
    );

    let schema = JSONSchema::compile(
        &serde_json::from_str(SCHEMA_JSON)
            .map_err(|e| anyhow!("Failed to parse schema: {}", e))?,
    )
    .map_err(|e| anyhow!("Failed to compile schema: {}", e))?;

    match validate_files_for_date(&s3_client, bucket_name, &source_prefix, &schema).await {
        Ok(result) => {
            if result.records_failed > 0 {
                let msg = format!(
                    "Validation failed: {} of {} records have schema violations",
                    result.records_failed, result.records_validated
                );
                println!("❌ {}", msg);
                Ok(create_error_response_with_data(&msg, result))
            } else {
                let msg = format!(
                    "Validation passed: all {} records in {} files conform to schema",
                    result.records_validated, result.files_validated
                );
                println!("✅ {}", msg);
                Ok(create_success_response(&msg, Some(result)))
            }
        }
        Err(e) => {
            eprintln!("Error during validation: {}", e);
            Ok(create_error_response(&format!("Validation error: {}", e)))
        }
    }
}

async fn validate_files_for_date(
    s3_client: &Client,
    bucket: &str,
    source_prefix: &str,
    schema: &JSONSchema,
) -> Result<ValidationResult> {
    let resp = s3_client
        .list_objects_v2()
        .bucket(bucket)
        .prefix(source_prefix)
        .send()
        .await?;

    let contents = resp.contents();
    if contents.is_empty() {
        println!("No files found in s3://{}/{}", bucket, source_prefix);
        return Ok(ValidationResult {
            source_prefix: source_prefix.to_string(),
            files_validated: 0,
            records_validated: 0,
            records_passed: 0,
            records_failed: 0,
            validation_errors: vec![],
        });
    }

    let re = Regex::new(r"/\d{8}\.json$")?;
    let json_keys: Vec<String> = contents
        .iter()
        .filter_map(|obj| {
            obj.key().and_then(|key| {
                if key.ends_with(".json") && re.is_match(key) {
                    Some(key.to_string())
                } else {
                    None
                }
            })
        })
        .collect();

    if json_keys.is_empty() {
        println!(
            "No matching JSON files found in s3://{}/{}",
            bucket, source_prefix
        );
        return Ok(ValidationResult {
            source_prefix: source_prefix.to_string(),
            files_validated: 0,
            records_validated: 0,
            records_passed: 0,
            records_failed: 0,
            validation_errors: vec![],
        });
    }

    println!("Found {} JSON files to validate", json_keys.len());

    let mut total_records = 0usize;
    let mut passed_records = 0usize;
    let mut failed_records = 0usize;
    let mut all_errors: Vec<RecordValidationError> = Vec::new();

    for key in &json_keys {
        match validate_single_file(s3_client, bucket, key, schema).await {
            Ok((record_count, errors)) => {
                total_records += record_count;
                let failed_in_file = errors.len();
                passed_records += record_count.saturating_sub(failed_in_file);
                failed_records += failed_in_file;
                all_errors.extend(errors);
                println!(
                    "Validated {} records from {} ({} failures)",
                    record_count,
                    key,
                    failed_in_file
                );
            }
            Err(e) => {
                eprintln!("Error validating file {}: {}", key, e);
                return Err(anyhow!("Error validating file {}: {}", key, e));
            }
        }
    }

    println!(
        "Validation summary: {} files, {} records ({} passed, {} failed)",
        json_keys.len(),
        total_records,
        passed_records,
        failed_records
    );

    Ok(ValidationResult {
        source_prefix: source_prefix.to_string(),
        files_validated: json_keys.len(),
        records_validated: total_records,
        records_passed: passed_records,
        records_failed: failed_records,
        validation_errors: all_errors,
    })
}

async fn validate_single_file(
    s3_client: &Client,
    bucket: &str,
    key: &str,
    schema: &JSONSchema,
) -> Result<(usize, Vec<RecordValidationError>)> {
    let obj = s3_client
        .get_object()
        .bucket(bucket)
        .key(key)
        .send()
        .await?;

    let data = obj.body.collect().await?.into_bytes();
    let cursor = Cursor::new(data);

    let json_value: serde_json::Value = serde_json::from_reader(cursor)
        .map_err(|e| anyhow!("Error parsing JSON from {}: {}", key, e))?;

    let records: Vec<serde_json::Value> = match json_value {
        serde_json::Value::Array(arr) => arr,
        serde_json::Value::Object(_) => vec![json_value],
        _ => return Err(anyhow!("Unexpected JSON structure in {}", key)),
    };

    let record_count = records.len();
    let mut errors = Vec::new();

    for (idx, record) in records.iter().enumerate() {
        let result = schema.validate(record);
        if let Err(validation_errors) = result {
            let error_messages: Vec<String> = validation_errors
                .map(|e: ValidationError| format!("{}: {}", e.instance_path, e))
                .collect();
            
            errors.push(RecordValidationError {
                file: key.to_string(),
                record_index: idx,
                errors: error_messages,
            });
        }
    }

    Ok((record_count, errors))
}

fn create_success_response(message: &str, data: Option<ValidationResult>) -> LambdaOutput {
    LambdaOutput {
        status_code: 200,
        success: true,
        message: message.to_string(),
        timestamp: Utc::now().to_rfc3339(),
        processor: "social-services-validator".to_string(),
        data,
    }
}

fn create_error_response(message: &str) -> LambdaOutput {
    LambdaOutput {
        status_code: 500,
        success: false,
        message: message.to_string(),
        timestamp: Utc::now().to_rfc3339(),
        processor: "social-services-validator".to_string(),
        data: None,
    }
}

fn create_error_response_with_data(message: &str, data: ValidationResult) -> LambdaOutput {
    LambdaOutput {
        status_code: 400,
        success: false,
        message: message.to_string(),
        timestamp: Utc::now().to_rfc3339(),
        processor: "social-services-validator".to_string(),
        data: Some(data),
    }
}
