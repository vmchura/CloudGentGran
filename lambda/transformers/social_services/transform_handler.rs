use aws_sdk_s3::{Client, types::ByteStream};
use aws_config::meta::region::RegionProviderChain;
use chrono::Utc;
use polars::prelude::*;
use regex::Regex;
use serde_json::Value;
use std::env;
use std::io::Cursor;
use anyhow::{Result, anyhow};

#[tokio::main]
async fn main() -> Result<()> {
    // Load AWS config
    let region_provider = RegionProviderChain::default_provider().or_else("eu-west-1");
    let shared_config = aws_config::from_env().region(region_provider).load().await;
    let s3_client = Client::new(&shared_config);

    // Example input
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

    let result = process_files_for_date(&s3_client, &bucket_name, &source_prefix, &target_key).await?;
    println!("Result: {:?}", result);

    Ok(())
}

async fn process_files_for_date(
    s3_client: &Client,
    bucket: &str,
    source_prefix: &str,
    target_key: &str
) -> Result<String> {
    // List files
    let resp = s3_client
        .list_objects_v2()
        .bucket(bucket)
        .prefix(source_prefix)
        .send()
        .await?;

    let re = Regex::new(r"/\d{8}\.json$")?;
    let mut json_keys = Vec::new();
    if let Some(contents) = resp.contents() {
        for obj in contents {
            if let Some(key) = obj.key() {
                if key.ends_with(".json") && re.is_match(key) {
                    json_keys.push(key.to_string());
                }
            }
        }
    }

    if json_keys.is_empty() {
        println!("No matching JSON files found in {}", source_prefix);
        return Ok("No files processed".to_string());
    }

    let mut dfs: Vec<DataFrame> = Vec::new();
    let mut total_raw_records = 0usize;

    // Download and parse each file
    for key in &json_keys {
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

        total_raw_records += df.height();
        dfs.push(df);
    }

    if dfs.is_empty() {
        return Err(anyhow!("No DataFrames created"));
    }

    // Combine
    let mut combined_df = concat_df(&dfs)?;

    // Transform
    combined_df = transform_social_services_data(combined_df)?;

    // Upload parquet
    upload_parquet_to_s3(s3_client, combined_df, bucket, target_key).await?;

    Ok(format!("Processed {} raw records", total_raw_records))
}

fn transform_social_services_data(mut df: DataFrame) -> Result<DataFrame> {
    // Remove empty rows: in Rust Polars, filter with any-not-null
    let mask = df
        .columns()
        .iter()
        .map(|s| s.is_not_null())
        .reduce(|acc, b| Ok(acc? | &b?))
        .unwrap()?;

    df = df.filter(&mask)?;

    // Add metadata columns
    let processed_timestamp = Series::new("processed_timestamp", vec![Utc::now().to_rfc3339(); df.height()]);
    let processor = Series::new("processor", vec!["social-services-transformer"; df.height()]);
    let environment = Series::new("environment", vec![env::var("ENVIRONMENT").unwrap_or_else(|_| "unknown".to_string()); df.height()]);

    df.with_column(processed_timestamp)?;
    df.with_column(processor)?;
    df.with_column(environment)?;

    // Deduplicate
    df = df.unique(None, UniqueKeepStrategy::First)?;

    Ok(df)
}

async fn upload_parquet_to_s3(s3_client: &Client, df: DataFrame, bucket: &str, s3_key: &str) -> Result<()> {
    let mut buf = Vec::new();
    ParquetWriter::new(&mut buf)
        .with_compression(ParquetCompression::Snappy)
        .finish(&df)?;

    s3_client
        .put_object()
        .bucket(bucket)
        .key(s3_key)
        .body(ByteStream::from(buf))
        .send()
        .await?;

    println!("Uploaded Parquet to s3://{}/{}", bucket, s3_key);
    Ok(())
}
