import {readParquetFromS3} from "./s3-parquet-reader.js";

const BUCKET = process.env.S3_BUCKET;

const data = await readParquetFromS3(BUCKET, "marts/population_municipal_greater_65/population_municipal_greater_65.parquet");
process.stdout.write(data);
