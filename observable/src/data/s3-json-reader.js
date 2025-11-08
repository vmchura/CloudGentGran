import {S3Client, GetObjectCommand, ListObjectsV2Command} from "@aws-sdk/client-s3";

const isLocal = process.env.AWS_PROFILE === "localstack";
const useLocalStack = process.env.AWS_ENDPOINT_URL?.includes('localstack') || process.env.AWS_ENDPOINT_URL?.includes('4566');

const s3Client = new S3Client(
  isLocal
    ? {
        endpoint: "http://localhost:4566",
        region: "us-west-1",
        forcePathStyle: true,
        credentials: {
          accessKeyId: "test",
          secretAccessKey: "test"
        }
      }
    : useLocalStack
    ? {
        endpoint: process.env.AWS_ENDPOINT_URL,
        region: process.env.AWS_REGION || "eu-west-1",
        forcePathStyle: true,
        credentials: {
          accessKeyId: process.env.AWS_ACCESS_KEY_ID,
          secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY
        }
      }
    : {
        region: process.env.AWS_REGION || "eu-west-1"
      }
);

async function streamToBuffer(stream) {
  const chunks = [];
  for await (const chunk of stream) {
    chunks.push(chunk);
  }
  return Buffer.concat(chunks);
}

export async function downloadObjectAsBuffer(bucket, key) {
  console.error(`Bucket: ${bucket}`);
  console.error(`Key: ${key}`);

  console.error(`Treating as single file`);
  console.error(`Downloading: s3://${bucket}/${key}`);
  const command = new GetObjectCommand({Bucket: bucket, Key: key});
  const response = await s3Client.send(command);
  const buffer = await streamToBuffer(response.Body);
  return buffer;
}
