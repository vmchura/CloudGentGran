import { S3Client, PutObjectCommand } from "@aws-sdk/client-s3";
import { execSync } from "child_process";
import fs from "fs";
import path from "path";

const s3 = new S3Client({
  endpoint: process.env.AWS_ENDPOINT_URL || undefined,
  forcePathStyle: true,
  region: process.env.REGION || 'eu-west-1'
});

export async function handler(event) {
    const bucketName = process.env.BUCKET_NAME;
    const repoUrl = process.env.REPOSITORY_URL;
    const targetPath = 'dist';
    const s3Prefix = 'dataservice/observable';
    const branch = process.env.ENVIRONMENT == 'prod' ? 'main' : 'develop';

    const tmpDir = `/tmp/repo-${Date.now()}`;

    try {
        
        console.log(`Cloning ${repoUrl}...`);
        
        execSync(`curl -L ${repoUrl}/archive/refs/heads/${branch}.zip -o ${tmpDir}/repo.zip`);
        execSync(`unzip ${tmpDir}/repo.zip "observable/*" -d ${tmpDir}`);
        

        console.log('Running npm ci...');
        execSync('npm ci', { cwd: tmpDir, stdio: 'inherit' });

        console.log('Running npm run build...');
        execSync('npm run build', { cwd: tmpDir, stdio: 'inherit' });

        let buildDir = path.join(tmpDir, targetPath);
        if (!fs.existsSync(buildDir)) {
            const distDir = path.join(tmpDir, 'dist');
            if (fs.existsSync(distDir)) {
                buildDir = distDir;
            } else {
                throw new Error(`Build output not found at ${targetPath} or dist`);
            }
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