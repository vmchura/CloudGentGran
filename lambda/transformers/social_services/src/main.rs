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

    // Get parameters directly from Airflow payload
    let downloaded_date = &event.payload.downloaded_date;
    let bucket_name = &event.payload.bucket_name;
    let semantic_identifier = &event.payload.semantic_identifier;

    println!("Processing files: s3://{}/landing/{}/downloaded_date={}", bucket_name, semantic_identifier, downloaded_date);

    let source_prefix = format!("landing/{}/downloaded_date={}/", semantic_identifier, downloaded_date);
    let target_key = format!("staging/{}/downloaded_date={}/{}.parquet", semantic_identifier,
    downloaded_date, Utc::now().format("%Y%m%d_%H%M%S"));

    match process_files_for_date(&s3_client, bucket_name, &source_prefix, &target_key).await {
        Ok(result) => {
            let glue_client = aws_sdk_glue::Client::new(&shared_config);
            let s3_prefix = format!("s3://{}/staging/social_services", bucket_name);
                add_partition_to_glue(
                    &glue_client,
                    &bucket_name,
                    "social_services",
                    downloaded_date,
                    &s3_prefix
                ).await?;
            Ok(create_success_response(
            &format!("Successfully processed files for date {}", downloaded_date),
            Some(result)
        ))},
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
    // Load catalog data - fail if environment variable not found
    let catalog_bucket = env::var("CATALOG_BUCKET_NAME").unwrap();

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


                dfs.push(df.select(&[
                                                   "registre",
                                                   "tipologia",
                                                   "inscripcio",
                                                   "capacitat",
                                                   "municipi",
                                                   "comarca",
                                                   "qualificacio"
                                               ])?);
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

    // Combine all dataframes
    println!("Concatenating {} dataframes", dfs.len());

    // Convert them all to lazy frames
    let lazy_frames: Vec<LazyFrame> = dfs.into_iter().map(|df| df.lazy()).collect();

    // Vertical concat (like UNION ALL)
    let merged_df = concat(lazy_frames, UnionArgs::default())?.collect()?;

    let transformed_df = transform_social_services_data(
                        merged_df,
                        municipals_df,
                        service_types_df,
                        service_qualification_df
                    )?;

    upload_parquet_to_s3(s3_client, &transformed_df, bucket, target_key).await?;

    println!("Successfully processed {} files -> {}", json_keys.len(), target_key);
    println!("Transformed {} raw records to {} clean records", total_raw_records, transformed_df.height());

    Ok(ProcessingResult {
        source_prefix: source_prefix.to_string(),
        target_key: target_key.to_string(),
        status: "success".to_string(),
        files_processed: json_keys.len(),
        raw_records: total_raw_records,
        clean_records: transformed_df.height(),
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
        .select(&[
            "registre",
            "tipologia",
            "inscripcio",
            "capacitat",
            "municipi",
            "comarca",
            "qualificacio"
        ])?
        .lazy()
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
        ])
        .collect()?;

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

    // Find the most recent parquet file
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

    // Create temporary file for parquet reading using std approach
    let temp_path = format!("/tmp/catalog_{}_{}.parquet", catalog_name, std::process::id());
    std::fs::write(&temp_path, &data)?;

    // Load parquet into Polars
    let df = LazyFrame::scan_parquet(&temp_path, ScanArgsParquet::default())?
        .collect()?;

    // Clean up temp file
    let _ = std::fs::remove_file(&temp_path);

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

fn normalize_text(text: &str) -> Vec<String> {
    let normalized = text
        .to_lowercase()
        .chars()
        .map(|c| match c {
            'á' | 'à' => 'a',
            'é' | 'è' => 'e',
            'í' | 'ì' => 'i',
            'ó' | 'ò' => 'o',
            'ú' | 'ù' => 'u',
            c if c.is_alphabetic() || c.is_whitespace() => c,
            _ => ' ',
        })
        .collect::<String>();

    // Split by whitespace and filter out single characters and empty strings
    normalized
        .split_whitespace()
        .filter(|token| token.len() > 1)
        .map(|s| s.to_string())
        .collect()
}

fn calculate_token_similarity(nom_tokens: &[String], municipi_tokens: &[String]) -> usize {
    let nom_set: HashSet<_> = nom_tokens.iter().collect();
    let municipi_set: HashSet<_> = municipi_tokens.iter().collect();
    nom_set.intersection(&municipi_set).count()
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
    df = df.select(&[
        "registre",
        "inscripcio",
        "capacitat",
        "municipi",
        "comarca",
        "service_type_id",
        "service_qualification_id"
    ])?;

    println!("After joins shape: {:?}", df.shape());

    // Join with municipals and normalize
    df = df.join(
        &municipals_df,
        ["comarca"],
        ["nom_comarca"],
        JoinArgs::new(JoinType::Left)
    )?;

    // Calculate normalized strings and similarities using a simpler approach
    let nom_series = df.column("nom")?;
    let municipi_series = df.column("municipi")?;

    let mut normalized_nom_strings: Vec<Option<String>> = Vec::new();
    let mut normalized_municipi_strings: Vec<Option<String>> = Vec::new();
    let mut similarities: Vec<i32> = Vec::new();

    for (nom_val, municipi_val) in nom_series.iter().zip(municipi_series.iter()) {
        match (nom_val.get_str(), municipi_val.get_str()) {
            (Some(nom_str), Some(municipi_str)) => {
                let nom_tokens = normalize_text(nom_str);
                let municipi_tokens = normalize_text(municipi_str);
                let similarity = calculate_token_similarity(&nom_tokens, &municipi_tokens) as i32;

                normalized_nom_strings.push(Some(nom_tokens.join(" ")));
                normalized_municipi_strings.push(Some(municipi_tokens.join(" ")));
                similarities.push(similarity);
            },
            _ => {
                normalized_nom_strings.push(None);
                normalized_municipi_strings.push(None);
                similarities.push(0);
            }
        }
    }

    // Create Series from the processed data and add to DataFrame using hstack
    let nom_normalized_series = Series::new("nom_normalized", normalized_nom_strings);
    let municipi_normalized_series = Series::new("municipi_normalized", normalized_municipi_strings);
    let tokens_similar_series = Series::new("tokens_similar", similarities);

    // Create a new DataFrame with additional columns
    let additional_df = DataFrame::new(vec![
        nom_normalized_series,
        municipi_normalized_series,
        tokens_similar_series,
    ])?;

    // Horizontally stack the additional columns
    df = df.hstack(&additional_df.get_columns())?;

    // Sort and deduplicate
    df = df.sort(
        ["registre", "tokens_similar"],
        SortMultipleOptions::default()
            .with_order_descending_multi([false, true])
    )?;

    // Remove duplicates keeping first (highest tokens_similar due to sort)
    df = df.unique(
        Some(&[
            "registre".to_string(),
            "inscripcio".to_string(),
            "capacitat".to_string(),
            "municipi".to_string(),
            "comarca".to_string(),
            "service_type_id".to_string(),
            "service_qualification_id".to_string()
        ]),
        UniqueKeepStrategy::First,
        None,
    )?;

    // Sort by tokens_similar
    df = df.sort(
        ["tokens_similar"],
        SortMultipleOptions::default()
    )?;

    // Select final columns with transformations
    let final_df = df.clone()
        .lazy()
        .with_columns([
            col("inscripcio")
                .str()
                .to_date(StrptimeOptions {
                    format: Some("%Y-%m-%d".into()),
                    ..Default::default()
                })
                .alias("inscription_date"),
            col("capacitat")
                .cast(DataType::Int32)
                .alias("capacity")
        ])
        .select([
            col("registre").alias("social_service_register_id"),
            col("inscription_date"),
            col("capacity"),
            col("service_type_id"),
            col("service_qualification_id"),
            col("codi").alias("municipal_id"),
            col("codi_comarca").alias("comarca_id")
        ])
        .collect()?;

    println!("Final DataFrame shape: {:?}", final_df.shape());
    println!("Final columns: {:?}", final_df.get_column_names());

    // Validate data integrity
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

async fn add_partition_to_glue(
    glue_client: &aws_sdk_glue::Client,
    database_name: &str,
    table_name: &str,
    downloaded_date: &str,
    s3_location: &str,
) -> Result<()> {
    let table_response = glue_client
        .get_table()
        .database_name(database_name)
        .name(table_name)
        .send()
        .await?;
    let table = table_response.table().ok_or_else(|| anyhow!("Table not found"))?;
    let base_storage_descriptor = table.storage_descriptor().ok_or_else(|| anyhow!("No storage descriptor"))?;
    let partition_storage_descriptor = aws_sdk_glue::types::StorageDescriptor::builder()
        .set_columns(base_storage_descriptor.columns().map(|cols| cols.to_vec()))
        .set_location(Some(format!("{}/downloaded_date={}/", s3_location, downloaded_date)))
        .set_input_format(base_storage_descriptor.input_format().map(|s| s.to_string()))
        .set_output_format(base_storage_descriptor.output_format().map(|s| s.to_string()))
        .set_compressed(base_storage_descriptor.compressed())
        .set_serde_info(base_storage_descriptor.serde_info().cloned())
        .build();
    let partition_input = aws_sdk_glue::types::PartitionInput::builder()
        .values(downloaded_date.to_string())
        .storage_descriptor(partition_storage_descriptor)
        .build();

    glue_client
        .create_partition()
        .database_name(database_name)
        .table_name(table_name)
        .partition_input(partition_input)
        .send()
        .await?;

    println!("Successfully created partition for {}/{} with date {}", database_name, table_name, downloaded_date);
    Ok(())
}
