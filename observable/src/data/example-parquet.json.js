import {readParquetFromS3} from "./parquet-reader.js";

const BUCKET = process.env.S3_BUCKET || "catalunya-data-dev";
const KEY = process.env.PARQUET_KEY || "marts/population_municipal_greater_65/population_municipal_greater_65.parquet";

const data = await readParquetFromS3(BUCKET, KEY);

process.stdout.write(JSON.stringify(data));
