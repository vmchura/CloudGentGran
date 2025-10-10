import {downloadObjectAsBuffer} from "./s3-json-reader.js";

const BUCKET = process.env.S3_BUCKET;

const data = await downloadObjectAsBuffer(BUCKET, "marts/comarques_boundaries/comarques-1000000.json");
process.stdout.write(data);
