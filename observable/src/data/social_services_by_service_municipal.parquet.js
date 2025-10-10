import {readParquetFromS3} from "./s3-parquet-reader.js";

const BUCKET = process.env.S3_BUCKET;

const data = await readParquetFromS3(BUCKET, "marts/social_services_by_service_municipal/");
process.stdout.write(data);
