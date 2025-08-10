// Local test script for the social services transformer
// Run with: cargo run --bin local_test

use aws_sdk_s3::{Client, primitives::ByteStream};
use aws_config::meta::region::RegionProviderChain;
use chrono::Utc;
use polars::prelude::*;
use regex::Regex;
use std::env;
use std::io::Cursor;
use anyhow::{Result, anyhow};

#[tokio::main]
async fn main() -> Result<()> {
    // Set up environment variables for testing
    env::set_var("BUCKET_NAME", "cloudgentgran-test-bucket"); // Replace with your actual bucket
    env::set_var("SEMANTIC_IDENTIFIER", "social_services");
    env::set_var("ENVIRONMENT", "dev");

    println!("🦀 Testing Rust Social Services Transformer");
    println!("============================================");

    // Load AWS config
    let region_provider = RegionProviderChain::default_provider().or_else("eu-west-1");
    let shared_config = aws_config::defaults(aws_config::BehaviorVersion::latest())
        .region(region_provider)
        .load()
        .await;
    let s3_client = Client::new(&shared_config);

    // Test with a sample date - change this to match your data
    let downloaded_date = "20250809";
    let bucket_name = env::var("BUCKET_NAME").unwrap();
    let semantic_identifier = env::var("SEMANTIC_IDENTIFIER").unwrap();

    let source_prefix = format!("landing/{}/downloaded_date={}/", semantic_identifier, downloaded_date);
    let target_key = format!(
        "staging/{}/transformed_date={}/social_services_{}.parquet",
        semantic_identifier,
        downloaded_date,
        Utc::now().format("%Y%m%d_%H%M%S")
    );

    println!("📂 Source: s3://{}/{}", bucket_name, source_prefix);
    println!("📦 Target: s3://{}/{}", bucket_name, target_key);
    println!("");

    match process_files_for_date(&s3_client, &bucket_name, &source_prefix, &target_key).await {
        Ok(result) => {
            println!("✅ SUCCESS!");
            println!("Files processed: {}", result.files_processed);
            println!("Raw records: {}", result.raw_records);
            println!("Clean records: {}", result.clean_records);
            println!("Target location: {}", result.target_location);
        }
        Err(e) => {
            println!("❌ ERROR: {}", e);
            std::process::exit(1);
        }
    }

    Ok(())
}

// Include all the processing functions from main.rs
// (In a real implementation, you'd structure this as a library crate)

#[derive(Debug)]
struct ProcessingResult {
    source_prefix: String,
    target_key: String,
    status: String,
    files_processed: usize,
    raw_records: usize,
    clean_records: usize,
    target_location: String,
}

async fn process_files_for_date(
    s3_client: &Client,
    bucket: &str,
    source_prefix: &str,
    target_key: &str
) -> Result<ProcessingResult> {
    println!("🔍 Listing files in s3://{}/{}", bucket, source_prefix);
    
    // List files
    let resp = s3_client
        .list_objects_v2()
        .bucket(bucket)
        .prefix(source_prefix)
        .send()
        .await?;

    let contents = resp.contents();
    if contents.is_empty() {
        println!("⚠️  No files found in s3://{}/{}", bucket, source_prefix);
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
        println!("⚠️  No matching JSON files found in s3://{}/{}", bucket, source_prefix);
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

    println!("📄 Found {} JSON files to process", json_keys.len());

    let mut dfs: Vec<DataFrame> = Vec::new();
    let mut total_raw_records = 0usize;

    // Download and parse each file
    for key in &json_keys {
        match process_single_file(s3_client, bucket, key).await {
            Ok((df, records)) => {
                total_raw_records += records;
                dfs.push(df);
                println!("   ✓ {}: {} records", key, records);
            }
            Err(e) => {
                println!("   ❌ {}: {}", key, e);
                continue;
            }
        }
    }

    if dfs.is_empty() {
        return Err(anyhow!("No DataFrames created from JSON files"));
    }

    // Combine all dataframes
    println!("🔄 Concatenating {} dataframes", dfs.len());
    let mut combined_df = if dfs.len() == 1 {
        dfs.into_iter().next().unwrap()
    } else {
        let mut result = dfs[0].clone();
        for df in dfs.iter().skip(1) {
            result = result.vstack(df)?;
        }
        result
    };

    // Transform
    println!("🔧 Applying transformations");
    combined_df = transform_social_services_data(combined_df)?;

    // Upload parquet
    println!("📤 Uploading to S3");
    upload_parquet_to_s3(s3_client, &combined_df, bucket, target_key).await?;

    println!("🎉 Successfully processed {} files -> {}", json_keys.len(), target_key);

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

fn transform_social_services_data(mut df: DataFrame) -> Result<DataFrame> {
    println!("   📊 Original DataFrame shape: {:?}", df.shape());

    // Remove empty rows: filter where any column is not null
    let mask = df
        .get_columns()
        .iter()
        .map(|s| s.is_not_null())
        .reduce(|acc, b| &acc | &b)
        .unwrap();

    df = df.filter(&mask)?;

    // Add metadata columns using direct Series addition
    let height = df.height();
    let processed_timestamp = Series::new("processed_timestamp", vec![Utc::now().to_rfc3339(); height]);
    let processor = Series::new("processor", vec!["social-services-transformer"; height]);
    let environment = Series::new("environment", vec![env::var("ENVIRONMENT").unwrap_or_else(|_| "unknown".to_string()); height]);
    
    df.with_column(processed_timestamp)?;
    df.with_column(processor)?;
    df.with_column(environment)?;

    // Deduplicate based on data columns (excluding metadata)
    let metadata_cols = vec!["processed_timestamp", "processor", "environment"];
    let data_cols: Vec<String> = df.get_column_names()
        .iter()
        .filter(|col| !metadata_cols.contains(col))
        .map(|col| col.to_string())
        .collect();

    if !data_cols.is_empty() {
        df = df.unique(Some(&data_cols), UniqueKeepStrategy::First, None)?;
    }

    println!("   📊 Final DataFrame shape: {:?}", df.shape());

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

    println!("   ✓ Uploaded {} bytes ({} records)", buf.len(), df.height());
    Ok(())
}
