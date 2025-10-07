use anyhow::Result;
use aws_config::meta::region::RegionProviderChain;
use aws_sdk_s3::Client;
use lambda_runtime::{Error, LambdaEvent};
use serde::{Deserialize, Serialize};
use std::env;

/// This is a made-up example. Incoming messages come into the runtime as unicode
/// strings in json format, which can map to any structure that implements `serde::Deserialize`
/// The runtime pays no attention to the contents of the incoming message payload.
#[derive(Deserialize)]
pub(crate) struct IncomingMessage {
    source_prefix: String,
}

/// This is a made-up example of what an outgoing message structure may look like.
/// There is no restriction on what it can be. The runtime requires responses
/// to be serialized into json. The runtime pays no attention
/// to the contents of the outgoing message payload.
#[derive(Serialize)]
pub(crate) struct OutgoingMessage {
    status: String,
    target_prefix: Option<String>,
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
    let bucket_name = env::var("BUCKET_NAME")?;
    let semantic_identifier = env::var("SEMANTIC_IDENTIFIER")?;
    let source_prefix = event.payload.source_prefix;
    let source_complete = format!("{}/{}", bucket_name, source_prefix);
    let region_provider = RegionProviderChain::default_provider().or_else("eu-west-1");
    let shared_config = aws_config::defaults(aws_config::BehaviorVersion::latest())
        .region(region_provider)
        .load()
        .await;
    let s3_client = Client::new(&shared_config);
    let target_key = format!(
        "marts/{}/{}.parquet",
        semantic_identifier, semantic_identifier
    );

    s3_client
        .copy_object()
        .copy_source(source_complete)
        .bucket(bucket_name)
        .key(&target_key)
        .send()
        .await?;

    // Prepare the outgoing message
    let resp = OutgoingMessage {
        status: "succeeded".to_string(),
        target_prefix: Some(target_key),
    };

    // Return `OutgoingMessage` (it will be serialized to JSON automatically by the runtime)
    Ok(resp)
}
