import {S3Client, GetObjectCommand} from "@aws-sdk/client-s3";
import {readParquet} from "parquet-wasm/node";

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

export async function readParquetFromS3(bucket, key) {
  console.error(bucket);
  console.error(key);
  const command = new GetObjectCommand({Bucket: bucket, Key: key});
  const response = await s3Client.send(command);
  const buffer = await streamToBuffer(response.Body);
  return buffer;
}