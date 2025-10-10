import {S3Client, GetObjectCommand, ListObjectsV2Command} from "@aws-sdk/client-s3";
import {readParquet, writeParquet} from "parquet-wasm/node";

const isLocal = process.env.AWS_PROFILE === "localstack";

const s3Client = new S3Client(
  isLocal
    ? {
        endpoint: "http://localhost:4566",
        region: "us-east-1",
        forcePathStyle: true,
        credentials: {
          accessKeyId: "test",
          secretAccessKey: "test"
        }
      }
    : {}
);

async function streamToBuffer(stream) {
  const chunks = [];
  for await (const chunk of stream) {
    chunks.push(chunk);
  }
  return Buffer.concat(chunks);
}

/**
 * Lists all objects under a given S3 prefix
 */
async function listS3Objects(bucket, prefix) {
  const objects = [];
  let continuationToken = undefined;

  do {
    const command = new ListObjectsV2Command({
      Bucket: bucket,
      Prefix: prefix,
      ContinuationToken: continuationToken
    });
    
    const response = await s3Client.send(command);
    
    if (response.Contents) {
      objects.push(...response.Contents);
    }
    
    continuationToken = response.NextContinuationToken;
  } while (continuationToken);

  return objects;
}

/**
 * Checks if a key points to a specific file or a directory pattern
 */
function isDirectoryPattern(key) {
  // If key ends with / or doesn't have an extension, treat as directory
  return key.endsWith('/') || !key.includes('.');
}


async function downloadObjectAsBuffer(bucket, key) {
  console.error(`Downloading: s3://${bucket}/${key}`);
  const command = new GetObjectCommand({Bucket: bucket, Key: key});
  const response = await s3Client.send(command);
  const buffer = await streamToBuffer(response.Body);
  return buffer;
}

function mergeParquetBuffers(buffers) {
  if (buffers.length === 0) {
    throw new Error("No parquet files found to merge");
  }
  
  if (buffers.length === 1) {
    return buffers[0];
  }
  const tables = buffers.map(single_buffer => readParquet(single_buffer));

  // For parquet-wasm, we need to convert to arrays and concatenate
  // Get column names from first table
  const columnNames = tables[0].schema.fields.map(f => f.name);
  
  // Merge data from all tables
  const mergedData = {};
  
  for (const colName of columnNames) {
    const allColumnData = [];
    for (const table of tables) {
      const column = table.getChild(colName);
      allColumnData.push(...column.toArray());
    }
    mergedData[colName] = allColumnData;
  }
  
  return writeParquet(mergedData);
}


export async function readParquetFromS3(bucket, key) {
  console.error(`Bucket: ${bucket}`);
  console.error(`Key: ${key}`);
  
  // Check if this is a directory pattern or specific file
  if (isDirectoryPattern(key)) {
    console.error(`Treating as directory pattern, listing all files...`);
    
    // List all objects under this prefix
    const objects = await listS3Objects(bucket, key);
    
    // Filter to only include files (not directories) and limit count
    const fileKeys = objects
      .filter(obj => !obj.Key.endsWith('/'))
      .map(obj => obj.Key);
    
    if (fileKeys.length === 0) {
      throw new Error(`No files found under s3://${bucket}/${key}`);
    }
    
    console.error(`Found ${fileKeys.length} file(s) to process`);
    
    // Download and parse all parquet files
    const buffers = await Promise.all(
      fileKeys.map(fileKey => downloadObjectAsBuffer(bucket, fileKey))
    );
    
    // Return merged or separate tables based on options
    console.error(`Merging ${buffers.length} parquet files...`);
    return mergeParquetBuffers(buffers);
  } else {
    // Single file download
    console.error(`Treating as single file`);
    return downloadObjectAsBuffer(bucket, key);
  }
}
