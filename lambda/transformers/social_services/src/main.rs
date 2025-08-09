use aws_sdk_s3::{Client, primitives::ByteStream};
use aws_config::meta::region::RegionProviderChain;
use chrono::Utc;
use polars::prelude::*;
use regex::Regex;
use std::env;
use std::io::Cursor;
use anyhow::{Result, anyhow};
use lambda_runtime::{service_fn, Error, LambdaEvent};
use serde::{Deserialize, Serialize};

#[derive(Deserialize, Serialize)]
struct LambdaInput {
    detail: Option<EventDetail>,
    downloaded_date: Option<String>,
}

#[derive(Deserialize, Serialize)]
struct EventDetail {
    downloaded_date: String,
    bucket_name: Option<String>,
    semantic_identifier: Option<String>,
}

#[derive(Serialize)]
struct LambdaOutput {
    #[serde(rename = "statusCode")]
    status_code: u16,
    success: bool,
    message: String,
    timestamp: String,
    processor: String,
    data: Option<ProcessingResult>,
}

#[derive(Serialize)]
struct ProcessingResult {
    source_prefix: String,
    target_key: String,
    status: String,
    files_processed: usize,
    raw_records: usize,
    clean_records: usize,
    target_location: String,
}

#[tokio::main]
async fn main() -> Result<(), Error> {
    lambda_runtime::run(service_fn(function_handler)).await
}

async fn function_handler(event: LambdaEvent<LambdaInput>) -> Result<LambdaOutput, Error> {
    println!("Starting transformation process at {}", Utc::now());
    println!("Received event: {}", serde_json::to_string(&event.payload)?);

    // Load AWS config
    let region_provider = RegionProviderChain::default_provider().or_else("eu-west-1");
    let shared_config = aws_config::defaults(aws_config::BehaviorVersion::latest())
        .region(region_provider)
        .load()
        .await;
    let s3_client = Client::new(&shared_config);

    // Parse event to get downloaded_date and other parameters
    let (downloaded_date, bucket_name, semantic_identifier) = match &event.payload {
        LambdaInput { detail: Some(detail), .. } => {
            // EventBridge custom event from API extractor
            let bucket = detail.bucket_name.clone()
                .or_else(|| env::var("BUCKET_NAME").ok())
                .ok_or_else(|| anyhow!("BUCKET_NAME not found"))?;
            let semantic = detail.semantic_identifier.clone()
                .or_else(|| env::var("SEMANTIC_IDENTIFIER").ok())
                .ok_or_else(|| anyhow!("SEMANTIC_IDENTIFIER not found"))?;
            (detail.downloaded_date.clone(), bucket, semantic)
        }
        _ => {
            let msg = "No downloaded_date found in event";
            return Ok(create_error_response(msg));
        }
    };

    println!("Processing files: s3://{}/landing/{}/downloaded_date={}", bucket_name, semantic_identifier, downloaded_date);

    let source_prefix = format!("landing/{}/downloaded_date={}/", semantic_identifier, downloaded_date);
    let target_key = format!(
        "staging/{}/transformed_date={}/social_services_{}.parquet",
        semantic_identifier,
        downloaded_date,
        Utc::now().format("%Y%m%d_%H%M%S")
    );

    match process_files_for_date(&s3_client, &bucket_name, &source_prefix, &target_key).await {
        Ok(result) => Ok(create_success_response(
            &format!("Successfully processed files for date {}", downloaded_date),
            Some(result)
        )),
        Err(e) => {
            eprintln!("Error in lambda_handler: {}", e);
            Ok(create_error_response(&format!("Handler error: {}", e)))
        }
    }
}

async fn process_files_for_date(
    s3_client: &Client,
    bucket: &str,
    source_prefix: &str,
    target_key: &str
) -> Result<ProcessingResult> {
    // List files
    let resp = s3_client
        .list_objects_v2()
        .bucket(bucket)
        .prefix(source_prefix)
        .send()
        .await?;

    let contents = resp.contents();
    if contents.is_empty() {
        println!("No files found in s3://{}/{}", bucket, source_prefix);
        return Ok(ProcessingResult {
            source_prefix: source_prefix.to_string(),
            target_key: target_key.to_string(),
            status: "success".to_string(),
            files_processed: 0,
            raw_records: 0,
            clean_records: 0,
            target_location: format!("s3://{}/{}", bucket, target_key),
        });
    }

    // Filter for JSON files with pattern XXXXXXXX.json (8 digits)
    let re = Regex::new(r"/\d{8}\.json$")?;
    let mut json_keys = Vec::new();
    for obj in contents {
        if let Some(key) = obj.key() {
            if key.ends_with(".json") && re.is_match(key) {
                json_keys.push(key.to_string());
            }
        }
    }

    if json_keys.is_empty() {
        println!("No matching JSON files found in s3://{}/{}", bucket, source_prefix);
        return Ok(ProcessingResult {
            source_prefix: source_prefix.to_string(),
            target_key: target_key.to_string(),
            status: "success".to_string(),
            files_processed: 0,
            raw_records: 0,
            clean_records: 0,
            target_location: format!("s3://{}/{}", bucket, target_key),
        });
    }

    println!("Found {} JSON files to process", json_keys.len());

    let mut dfs: Vec<DataFrame> = Vec::new();
    let mut total_raw_records = 0usize;

    // Download and parse each file
    for key in &json_keys {
        match process_single_file(s3_client, bucket, key).await {
            Ok((df, records)) => {
                total_raw_records += records;
                dfs.push(df);
                println!("Read {} records from {}", records, key);
            }
            Err(e) => {
                eprintln!("Error processing file {}: {}", key, e);
                return Err(anyhow!("Error processing file {}: {}", key, e));
            }
        }
    }

    if dfs.is_empty() {
        return Err(anyhow!("No DataFrames created from JSON files"));
    }

    // Combine all dataframes "softly" like pandas (fill missing columns with nulls)
    println!("Concatenating {} dataframes", dfs.len());

    let mut combined_df = if dfs.len() == 1 {
        dfs.into_iter().next().unwrap()
    } else {
        // Step 1: collect all unique columns across all dfs
        let mut all_columns: Vec<String> = dfs
            .iter()
            .flat_map(|df| df.get_column_names().into_iter().map(|s| s.to_string()))
            .collect();
        all_columns.sort();
        all_columns.dedup();

        // Step 2: align each df to have all columns
        let aligned_dfs: Vec<DataFrame> = dfs
            .iter()
            .map(|df| {
                let mut df = df.clone();
                for col in &all_columns {
                    if !df.get_column_names().contains(&col.as_str()) {
                        // Use String type for missing columns
                        let null_series = Series::full_null(col, df.height(), &DataType::String);
                        df.with_column(null_series)?;
                    }
                }
                df.select(&all_columns)
            })
            .collect::<PolarsResult<Vec<_>>>()?;

        // Step 3: concatenate aligned dfs
        let mut result_df = aligned_dfs[0].clone();
        for df in aligned_dfs.iter().skip(1) {
            result_df.vstack_mut(df)?;
        }
        result_df
    };


    combined_df = transform_social_services_data(combined_df)?;
    upload_parquet_to_s3(s3_client, &combined_df, bucket, target_key).await?;

    println!("Successfully processed {} files -> {}", json_keys.len(), target_key);
    println!("Transformed {} raw records to {} clean records", total_raw_records, combined_df.height());

    Ok(ProcessingResult {
        source_prefix: source_prefix.to_string(),
        target_key: target_key.to_string(),
        status: "success".to_string(),
        files_processed: json_keys.len(),
        raw_records: total_raw_records,
        clean_records: combined_df.height(),
        target_location: format!("s3://{}/{}", bucket, target_key),
    })
}

async fn process_single_file(s3_client: &Client, bucket: &str, key: &str) -> Result<(DataFrame, usize)> {
    let obj = s3_client
        .get_object()
        .bucket(bucket)
        .key(key)
        .send()
        .await?;

    let data = obj.body.collect().await?.into_bytes();
    let cursor = Cursor::new(data);

    // Load JSON into Polars
    let df = JsonReader::new(cursor)
        .finish()
        .map_err(|e| anyhow!("Error reading {}: {}", key, e))?;

    let record_count = df.height();
    Ok((df, record_count))
}

fn transform_social_services_data(df: DataFrame) -> Result<DataFrame> {
    println!("Original DataFrame shape: {:?}", df.shape());
    println!("Original columns: {:?}", df.get_column_names());

    println!("Final DataFrame shape: {:?}", df.shape());
    println!("Final columns: {:?}", df.get_column_names());

    Ok(df)
}

async fn upload_parquet_to_s3(s3_client: &Client, df: &DataFrame, bucket: &str, s3_key: &str) -> Result<()> {
    let mut buf = Vec::new();
    ParquetWriter::new(&mut buf)
        .with_compression(ParquetCompression::Snappy)
        .finish(&mut df.clone())?;

    s3_client
        .put_object()
        .bucket(bucket)
        .key(s3_key)
        .body(ByteStream::from(buf.clone()))
        .content_type("application/octet-stream")
        .metadata("transformer", "social-services-transformer")
        .metadata("format", "parquet")
        .metadata("record_count", &df.height().to_string())
        .metadata("processed_timestamp", &Utc::now().to_rfc3339())
        .metadata("columns", &df.get_column_names().join(","))
        .send()
        .await?;

    println!("Successfully uploaded Parquet file to s3://{}/{}", bucket, s3_key);
    println!("File size: {} bytes, Records: {}", buf.len(), df.height());
    Ok(())
}

fn create_success_response(message: &str, data: Option<ProcessingResult>) -> LambdaOutput {
    LambdaOutput {
        status_code: 200,
        success: true,
        message: message.to_string(),
        timestamp: Utc::now().to_rfc3339(),
        processor: "social-services-transformer".to_string(),
        data,
    }
}

fn create_error_response(message: &str) -> LambdaOutput {
    LambdaOutput {
        status_code: 500,
        success: false,
        message: message.to_string(),
        timestamp: Utc::now().to_rfc3339(),
        processor: "social-services-transformer".to_string(),
        data: None,
    }
}
