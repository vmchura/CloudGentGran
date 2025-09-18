/*
 * Social Services Data Transformer Lambda
 *
 * This Lambda function processes social services data from Catalonia and performs the following transformations:
 *
 * 1. Loads catalog data from S3:
 *    - municipals: Municipality information with comarca (county) mappings
 *    - service_type: Service type classifications and descriptions
 *    - service_qualification: Service qualification types (public/private)
 *
 * 2. Processes social services JSON files from the landing bucket:
 *    - Reads multiple JSON files with social services data
 *    - Cleans data (handles null values, comarca name standardization)
 *    - Validates that all service types and qualifications exist in catalogs
 *
 * 3. Performs data enrichment through joins:
 *    - Maps service type descriptions to IDs
 *    - Maps service qualification descriptions to IDs
 *    - Maps comarca names to municipality codes
 *
 * 4. Municipality name matching:
 *    - Normalizes municipality names (removes accents, special chars)
 *    - Tokenizes normalized names and calculates similarity scores
 *    - Handles cases where municipality names don't exactly match catalog
 *
 * 5. Data deduplication and final transformations:
 *    - Removes duplicates keeping best municipality matches
 *    - Converts data types (dates, integers)
 *    - Produces final schema with standardized column names
 *
 * Output: Parquet file in staging bucket with normalized social services data
 * ready for analytics and reporting.
 */

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
use std::collections::HashSet;

#[derive(Deserialize, Serialize)]
struct LambdaInput {
    detail: Option<EventDetail>,
    downloaded_date: Option<String>,
    bucket_name: Option<String>,
    semantic_identifier: Option<String>,
    extraction_timestamp: Option<String>,
    file_count: Option<u32>,
    source_prefix: Option<String>,
    total_records: Option<u32>,
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
        LambdaInput {
            downloaded_date: Some(date),
            bucket_name: Some(bucket),
            semantic_identifier: Some(semantic),
            ..
        } => {
            // Direct invocation from Airflow DAG with full payload
            (date.clone(), bucket.clone(), semantic.clone())
        }
        LambdaInput { downloaded_date: Some(date), .. } => {
            // Direct invocation from Airflow DAG with minimal payload
            let bucket = event.payload.bucket_name.clone()
                .or_else(|| env::var("BUCKET_NAME").ok())
                .unwrap_or_else(|| "catalunya-data-dev".to_string()); // Default for LocalStack
            let semantic = event.payload.semantic_identifier.clone()
                .or_else(|| env::var("SEMANTIC_IDENTIFIER").ok())
                .unwrap_or_else(|| "social_services".to_string()); // Default semantic identifier
            (date.clone(), bucket, semantic)
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
    // First, load catalog data
    let catalog_bucket = env::var("CATALOG_BUCKET_NAME")
        .unwrap_or_else(|_| "catalunya-catalog-dev".to_string());

    println!("Loading catalog data from bucket: {}", catalog_bucket);

    let municipals_df = load_catalog_data(s3_client, &catalog_bucket, "municipals").await?;
    let service_types_df = load_catalog_data(s3_client, &catalog_bucket, "service_type").await?;
    let service_qualification_df = load_catalog_data(s3_client, &catalog_bucket, "service_qualification").await?;

    println!("Loaded catalogs - municipals: {}, service_types: {}, service_qualification: {}",
             municipals_df.height(), service_types_df.height(), service_qualification_df.height());

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

    // Transform the data with catalogs
    combined_df = transform_social_services_data(
        combined_df,
        municipals_df,
        service_types_df,
        service_qualification_df
    )?;

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

    // Load JSON into Polars, selecting only the required columns
    let df = JsonReader::new(cursor)
        .finish()
        .map_err(|e| anyhow!("Error reading {}: {}", key, e))?
        .select([
            col("registre"),
            col("tipologia"),
            col("inscripcio"),
            col("capacitat"),
            col("municipi"),
            col("comarca"),
            col("qualificacio")
        ])?
        .with_columns([
            // Replace "null" string with actual null
            when(col("qualificacio").eq(lit("null")))
                .then(lit(NULL))
                .otherwise(col("qualificacio"))
                .alias("qualificacio"),
            // Replace "Val d'Aran" with "Aran"
            when(col("comarca").eq(lit("Val d'Aran")))
                .then(lit("Aran"))
                .otherwise(col("comarca"))
                .alias("comarca")
        ])?;

    let record_count = df.height();
    Ok((df, record_count))
}

async fn load_catalog_data(s3_client: &Client, bucket: &str, catalog_name: &str) -> Result<DataFrame> {
    println!("Loading catalog: {}", catalog_name);

    // List all parquet files in the catalog folder
    let resp = s3_client
        .list_objects_v2()
        .bucket(bucket)
        .prefix(&format!("{}/", catalog_name))
        .send()
        .await?;

    let contents = resp.contents();
    if contents.is_empty() {
        return Err(anyhow!("No catalog files found for {}", catalog_name));
    }

    // Find the most recent parquet file
    let mut parquet_keys: Vec<String> = contents
        .iter()
        .filter_map(|obj| {
            obj.key().and_then(|key| {
                if key.ends_with(".parquet") {
                    Some(key.to_string())
                } else {
                    None
                }
            })
        })
        .collect();

    if parquet_keys.is_empty() {
        return Err(anyhow!("No parquet files found for catalog {}", catalog_name));
    }

    // Sort to get the most recent file (by timestamp in filename)
    parquet_keys.sort();
    let latest_key = parquet_keys.last().unwrap();

    println!("Loading catalog file: {}", latest_key);

    // Download the parquet file
    let obj = s3_client
        .get_object()
        .bucket(bucket)
        .key(latest_key)
        .send()
        .await?;

    let data = obj.body.collect().await?.into_bytes();
    let cursor = Cursor::new(data);

    // Load parquet into Polars
    let df = LazyFrame::scan_parquet(cursor, ScanArgsParquet::default())?
        .collect()?;

    println!("Loaded catalog {} with {} rows", catalog_name, df.height());
    Ok(df)
}

fn has_unmapped_element(
    left_series: &Series,
    right_series: &Series,
    allow_null_left: bool,
    prefix: &str
) -> Result<Vec<String>> {
    let mut errors = Vec::new();

    let left_unique = left_series.unique()?.sort(Default::default())?;
    let right_unique = right_series.unique()?.sort(Default::default())?;

    // Convert to HashSet for faster lookup
    let right_set: HashSet<String> = right_unique
        .iter()
        .filter_map(|val| {
            if val.is_null() {
                None
            } else {
                Some(val.to_string().replace("\"", ""))
            }
        })
        .collect();

    for val in left_unique.iter() {
        if val.is_null() {
            if !allow_null_left {
                errors.push(format!("[{}]: Null value in left series", prefix));
            }
        } else {
            let val_str = val.to_string().replace("\"", "");
            if !right_set.contains(&val_str) {
                errors.push(format!("[{}]: Value `{}` not in right series", prefix, val_str));
            }
        }
    }

    Ok(errors)
}

fn normalize_expr() -> Expr {
    col("")
        .str().to_lowercase()
        .str().replace_all(lit(r"[áà]"), lit("a"), false)
        .str().replace_all(lit(r"[éè]"), lit("e"), false)
        .str().replace_all(lit(r"[íì]"), lit("i"), false)
        .str().replace_all(lit(r"[óò]"), lit("o"), false)
        .str().replace_all(lit(r"[úù]"), lit("u"), false)
        .str().replace_all(lit(r"[^a-z\s]"), lit(" "), false)
        .str().replace_all(lit(r"\s+"), lit(" "), false)
        .str().strip_chars(None)
        .str().split(lit(" "))
        .list().eval(col("").filter(col("").str().len_chars().gt(lit(1))), false)
}

fn transform_social_services_data(
    mut df: DataFrame,
    municipals_df: DataFrame,
    service_types_df: DataFrame,
    service_qualification_df: DataFrame
) -> Result<DataFrame> {
    println!("Original DataFrame shape: {:?}", df.shape());
    println!("Original columns: {:?}", df.get_column_names());

    // Validate mappings
    let mut errors = Vec::new();

    // Check service types mapping
    let tipologia_series = df.column("tipologia")?;
    let service_type_desc_series = service_types_df.column("service_type_description")?;
    errors.extend(has_unmapped_element(tipologia_series, service_type_desc_series, false, "service_type")?);

    // Check service qualification mapping
    let qualificacio_series = df.column("qualificacio")?;
    let service_qual_desc_series = service_qualification_df.column("service_qualification_description")?;
    errors.extend(has_unmapped_element(qualificacio_series, service_qual_desc_series, true, "service_qualification")?);

    if !errors.is_empty() {
        for error in &errors {
            eprintln!("Validation error: {}", error);
        }
        return Err(anyhow!("Validation failed with {} errors", errors.len()));
    }

    println!("Mapping validation passed");

    // Join with service types
    df = df.join(
        &service_types_df,
        ["tipologia"],
        ["service_type_description"],
        JoinArgs::new(JoinType::Left)
    )?;

    // Join with service qualification
    df = df.join(
        &service_qualification_df,
        ["qualificacio"],
        ["service_qualification_description"],
        JoinArgs::new(JoinType::Left)
    )?;

    // Select intermediate columns
    df = df.select([
        col("registre"),
        col("inscripcio"),
        col("capacitat"),
        col("municipi"),
        col("comarca"),
        col("service_type_id"),
        col("service_qualification_id")
    ])?;

    println!("After joins shape: {:?}", df.shape());

    // Join with municipals and normalize
    df = df.join(
        &municipals_df,
        ["comarca"],
        ["nom_comarca"],
        JoinArgs::new(JoinType::Left)
    )?;

    // Add normalized columns and token similarity
    let normalize_nom = normalize_expr().map_alias(|_| "nom_normalized".into());
    let normalize_municipi = normalize_expr().map_alias(|_| "municipi_normalized".into());

    df = df.with_columns([
        col("nom").apply(normalize_nom, GetOutput::default()).alias("nom_normalized"),
        col("municipi").apply(normalize_municipi, GetOutput::default()).alias("municipi_normalized")
    ])?;

    // Calculate token intersection length
    df = df.with_columns([
        col("nom_normalized")
            .list()
            .set_intersection(col("municipi_normalized"))
            .list()
            .len()
            .alias("tokens_similar")
    ])?;

    // Sort and deduplicate
    df = df.sort(
        ["registre", "tokens_similar"],
        SortMultipleOptions::default()
            .with_order_descending_multi([false, true])
    )?;

    // Remove duplicates keeping first (highest tokens_similar due to sort)
    df = df.unique(
        Some(vec![
            "registre".to_string(),
            "inscripcio".to_string(),
            "capacitat".to_string(),
            "municipi".to_string(),
            "comarca".to_string(),
            "service_type_id".to_string(),
            "service_qualification_id".to_string()
        ]),
        UniqueKeepStrategy::First,
    )?;

    // Final sort by tokens_similar
    df = df.sort(
        ["tokens_similar"],
        SortMultipleOptions::default()
    )?;

    // Select final columns with transformations
    let final_df = df.select([
        col("registre").alias("social_service_register_id"),
        col("inscripcio")
            .str()
            .to_date(StrptimeOptions::default().with_format(Some("%Y-%m-%d".to_string())))
            .alias("inscription_date"),
        col("capacitat")
            .str()
            .to_integer(false)
            .alias("capacity"),
        col("service_type_id"),
        col("service_qualification_id"),
        col("codi").alias("municipal_id"),
        col("codi_comarca").alias("comarca_id")
    ])?;

    println!("Final DataFrame shape: {:?}", final_df.shape());
    println!("Final columns: {:?}", final_df.get_column_names());

    // Validate that we haven't lost any unique registre values
    let original_unique_registre = df.column("registre")?.unique()?.len();
    let final_unique_registre = final_df.column("social_service_register_id")?.unique()?.len();

    if original_unique_registre != final_unique_registre {
        return Err(anyhow!(
            "Data integrity check failed: original unique registre count ({}) != final count ({})",
            original_unique_registre, final_unique_registre
        ));
    }

    if final_unique_registre == 0 {
        return Err(anyhow!("No records in final dataset"));
    }

    println!("Data integrity check passed: {} unique records preserved", final_unique_registre);

    Ok(final_df)
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
