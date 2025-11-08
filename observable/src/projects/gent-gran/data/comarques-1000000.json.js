import {downloadObjectAsBuffer} from "../../../data/s3-json-reader.js";

const BUCKET = process.env.S3_BUCKET_DATA;

const data = await downloadObjectAsBuffer(BUCKET, "marts/comarques_boundaries/comarques-1000000.json");
process.stdout.write(data);
