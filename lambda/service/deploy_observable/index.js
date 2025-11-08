import { S3Client, PutObjectCommand } from "@aws-sdk/client-s3";
import fs from "fs";
import path from "path";
import https from "https";
import { pipeline } from "stream/promises";
import { createWriteStream } from "fs";
import AdmZip from "adm-zip";
import { execSync } from "child_process";


const s3 = new S3Client({
  endpoint: process.env.AWS_ENDPOINT_URL || undefined,
  forcePathStyle: true,
  region: process.env.REGION || 'eu-west-1'
});

async function downloadFile(url, destPath) {
  const file = createWriteStream(destPath);
  return new Promise((resolve, reject) => {
    https.get(url, (response) => {
      if (response.statusCode === 302 || response.statusCode === 301) {
        // Follow redirect
        return downloadFile(response.headers.location, destPath).then(resolve).catch(reject);
      }
      response.pipe(file);
      file.on('finish', () => {
        file.close();
        resolve();
      });
    }).on('error', (err) => {
      fs.unlink(destPath, () => reject(err));
    });
  });
}


export async function handler(event) {
    const bucketName = process.env.BUCKET_NAME;
    const repoUrl = process.env.REPOSITORY_URL;
    const s3Prefix = 'dataservice/observable';
    const branch = process.env.ENVIRONMENT == 'prod' ? 'main' : 'develop';

    const tmpDir = `/tmp/repo-${Date.now()}`;
    const zipPath = path.join(tmpDir, 'repo.zip');
    const observableDirectory = path.join(tmpDir, `CloudGentGran-${branch}`, 'observable');

    try {
        
        console.log(`Get ${repoUrl}/${branch}... into ${observableDirectory}`);
        
        // Create temp directory
        fs.mkdirSync(tmpDir, { recursive: true });
        
        // Download zip file
        const downloadUrl = `${repoUrl}/archive/refs/heads/${branch}.zip`;
        console.log(`Downloading from ${downloadUrl}`);
        await downloadFile(downloadUrl, zipPath);
        
        // Extract zip file
        console.log('Extracting zip file...');
        const zip = new AdmZip(zipPath);
        
        // Extract only files that match the pattern
        zip.extractEntryTo(
            `CloudGentGran-${branch}/observable/`,
            tmpDir,
            true,  // maintainEntryPath
            true   // overwrite
        );
        
        console.log(`Extracted to ${observableDirectory}`);
        execSync(`chmod -R 755 ${tmpDir}`);

        

        console.log('Running npm ci...');
        execSync('npm ci', { cwd: observableDirectory, stdio: 'inherit' });

        console.log('Running npm run build...');
        execSync('npm run build', { cwd: observableDirectory, stdio: 'inherit' });

        let buildDir = path.join(observableDirectory, 'dist');
        if (!fs.existsSync(buildDir)) {
           
            throw new Error(`Build output not found at ${buildDir}`);
        }

        console.log(`Uploading from ${buildDir} to s3://${bucketName}/${s3Prefix}...`);
        const uploadedFiles = await uploadDirectory(buildDir, bucketName, s3Prefix);

        execSync(`rm -rf ${tmpDir}`, { stdio: 'pipe' });

        return {
            statusCode: 200,
            body: JSON.stringify({
                status: 'succeeded',
                bucket: bucketName,
                prefix: s3Prefix,
                uploaded_files: uploadedFiles.length,
                files: uploadedFiles.slice(0, 10)
            })
        };
    } catch (error) {
        try { execSync(`rm -rf ${tmpDir}`, { stdio: 'pipe' }); } catch(e) {}
        console.error('Error:', error);
        return {
            statusCode: 500,
            body: JSON.stringify({
                status: 'failed',
                error: error.message,
                stack: error.stack
            })
        };
    }
};

async function uploadDirectory(dirPath, bucket, prefix) {
    const files = [];
    const items = fs.readdirSync(dirPath, { withFileTypes: true });

    for (const item of items) {
        const fullPath = path.join(dirPath, item.name);
        if (item.isDirectory()) {
            const subFiles = await uploadDirectory(fullPath, bucket, `${prefix}/${item.name}`);
            files.push(...subFiles);
        } else {
            const key = `${prefix}/${item.name}`;
            const fileContent = fs.readFileSync(fullPath);
            await s3.send(new PutObjectCommand({
                Bucket: bucket,
                Key: key,
                Body: fileContent
            }));
            files.push(key);
        }
    }
    return files;
}

if (import.meta.url === `file://${process.argv[1]}`) {
    handler({}).then(result => {
        console.log('Result:', JSON.stringify(result, null, 2));
        process.exit(result.statusCode === 200 ? 0 : 1);
    }).catch(err => {
        console.error('Fatal error:', err);
        process.exit(1);
    });
}