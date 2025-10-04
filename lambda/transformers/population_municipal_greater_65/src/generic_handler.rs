use anyhow::{anyhow, Result};
use aws_config::meta::region::RegionProviderChain;
use aws_sdk_s3::{primitives::ByteStream, Client};
use chrono::Utc;
use lambda_runtime::{Error, LambdaEvent};
use polars::prelude::*;
use regex::Regex;
use serde::{Deserialize, Serialize};
use serde_json::Value;
/// This is a made-up example. Incoming messages come into the runtime as unicode
/// strings in json format, which can map to any structure that implements `serde::Deserialize`
/// The runtime pays no attention to the contents of the incoming message payload.
#[derive(Deserialize)]
pub(crate) struct IncomingMessage {
    bucket_name: String,
    semantic_identifier: String,
    source_prefix: String,
}

/// This is a made-up example of what an outgoing message structure may look like.
/// There is no restriction on what it can be. The runtime requires responses
/// to be serialized into json. The runtime pays no attention
/// to the contents of the outgoing message payload.
#[derive(Serialize)]
pub(crate) struct OutgoingMessage {
    status: String,
}

/// This is the main body for the function.
/// Write your code inside it.
/// There are some code example in the following URLs:
/// - https://github.com/awslabs/aws-lambda-rust-runtime/tree/main/examples
/// - https://github.com/aws-samples/serverless-rust-demo/
pub(crate) async fn function_handler(
    event: LambdaEvent<IncomingMessage>,
) -> Result<OutgoingMessage, Error> {
    // Extract some useful info from the request
    let bucket_name = event.payload.bucket_name;
    let semantic_identifier = event.payload.semantic_identifier;
    let source_prefix = event.payload.source_prefix;
    let region_provider = RegionProviderChain::default_provider().or_else("eu-west-1");
    let shared_config = aws_config::defaults(aws_config::BehaviorVersion::latest())
        .region(region_provider)
        .load()
        .await;
    let s3_client = Client::new(&shared_config);
    let target_key = format!(
        "staging/{}/{}.parquet",
        semantic_identifier, semantic_identifier
    );
    let resp = s3_client
        .list_objects_v2()
        .bucket(bucket_name)
        .prefix(source_prefix)
        .send()
        .await?;

    let contents = resp.contents();

    let re = Regex::new(r"/\d{4}\.json$")?;
    let json_keys: Vec<String> = contents
        .iter()
        .filter_map(|obj| {
            obj.key().and_then(|key| {
                if re.is_match(key) {
                    Some(key.to_string())
                } else {
                    None
                }
            })
        })
        .collect();
    if json_keys.is_empty() {
        println!(
            "No files found in s3://{}/{} with format {}",
            bucket_name,
            source_prefix,
            re.to_string()
        );
        return Ok(OutgoingMessage {
            status: "failed".to_string(),
        });
    }
    let mut dfs: Vec<DataFrame> = Vec::new();
    for key in &json_keys {
        match process_single_file(&s3_client, &bucket_name, key).await {
            Ok(df) => {
                dfs.push(df);
                println!("Read {} records from {}", df.height(), key);
            }
            Err(e) => {
                eprintln!("Error processing file {}: {}", key, e);
                Err(anyhow!("Error processing file {}: {}", key, e).into());
            }
        }
    }
    let lazy_frames: Vec<LazyFrame> = dfs.into_iter().map(|df| df.lazy()).collect();
    let merged_df = concat(lazy_frames, UnionArgs::default())?.collect()?;

    upload_parquet_to_s3(&s3_client, &merged_df, &bucket_name, &target_key).await?;

    // Prepare the outgoing message
    let resp = OutgoingMessage {
        status: "succeeded".to_string(),
    };

    // Return `OutgoingMessage` (it will be serialized to JSON automatically by the runtime)
    Ok(resp)
}

async fn process_single_file(s3_client: &Client, bucket: &str, key: &str) -> Result<DataFrame> {
    let obj = s3_client
        .get_object()
        .bucket(bucket)
        .key(key)
        .send()
        .await?;

    let data = obj.body.collect().await?.into_bytes();

    let json_value: Value = serde_json::from_slice(&data)?;

    let total_items = json_value["size"]
        .as_array()
        .ok_or_else(|| anyhow!("sizes are not an aray"))?
        .iter()
        .map(|v| {
            v.as_u64()
                .ok_or_else(|| anyhow!("size value not an integer"))
        })
        .try_fold(1, |acc, x| x.map(|val| acc * val))?;

    let total_height = (total_items / 2 - 1) as usize;

    let year_index = json_value["dimension"]["YEAR"]["category"]["index"]
        .as_array()
        .ok_or_else(|| anyhow!("municipal_codes_and_total not array"))?;

    if year_index.len() != 1 {
        return Err(anyhow!(
            "expected exactly 1 year index, got {}",
            year_index.len()
        ));
    }

    let year_value = year_index[0]
        .as_str()
        .ok_or_else(|| anyhow!("year index is not a string"))?
        .parse::<i64>()
        .map_err(|e| anyhow!("failed to parse year index as integer: {e}"))?;

    let municipal_codes_and_total = json_value["dimension"]["MUN"]["category"]["index"]
        .as_array()
        .ok_or_else(|| anyhow!("municipal_codes_and_total not array"))?;

    let population_values = json_value["value"]
        .as_array()
        .ok_or_else(|| anyhow!("population_values not array"))?;

    let municipal_codes: Vec<String> = municipal_codes_and_total
        [..municipal_codes_and_total.len() - 1]
        .iter()
        .map(|x| x.as_str().unwrap().to_string())
        .collect();

    let pop_ge65: Vec<i64> = population_values
        .iter()
        .enumerate()
        .filter_map(|(i, v)| (i % 2 == 0).then(|| v.as_i64()).flatten())
        .collect::<Vec<_>>()
        .into_iter()
        .take(population_values.len() / 2 - 1) // skip last one
        .collect();

    let pop_total: Vec<i64> = population_values
        .iter()
        .enumerate()
        .filter_map(|(i, v)| (i % 2 == 1).then(|| v.as_i64()).flatten())
        .collect::<Vec<_>>()
        .into_iter()
        .take(population_values.len() / 2 - 1) // skip last one
        .collect();

    let s_codes = Series::new("municipal_code".into(), municipal_codes);
    let s_ge65 = Series::new("population_ge65".into(), pop_ge65);
    let s_pop = Series::new("population".into(), pop_total);
    let year_series = Series::new("year".into(), vec![year_value; total_height]);

    let df = DataFrame::new(vec![
        s_codes.into_column(),
        s_ge65.into_column(),
        s_pop.into_column(),
        year_series.into_column(),
    ])?;

    Ok(df)
}

async fn upload_parquet_to_s3(
    s3_client: &Client,
    df: &DataFrame,
    bucket: &str,
    s3_key: &str,
) -> Result<()> {
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
        .metadata("transformer", "population_municipal_greater_65")
        .metadata("format", "parquet")
        .metadata("record_count", &df.height().to_string())
        .metadata("processed_timestamp", &Utc::now().to_rfc3339())
        .metadata(
            "columns",
            &df.get_column_names()
                .iter()
                .map(|s| s.as_str()) // convert &PlSmallStr → &str
                .collect::<Vec<_>>()
                .join(","),
        )
        .send()
        .await?;

    println!(
        "Successfully uploaded Parquet file to s3://{}/{}",
        bucket, s3_key
    );
    println!("File size: {} bytes, Records: {}", buf.len(), df.height());
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use lambda_runtime::{Context, LambdaEvent};

    #[tokio::test]
    async fn test_generic_handler() {
        let event = LambdaEvent::new(
            IncomingMessage {
                command: "test".to_string(),
            },
            Context::default(),
        );
        let response = function_handler(event).await.unwrap();
        assert_eq!(response.msg, "Command test.");
    }
}
