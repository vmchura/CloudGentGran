const AWS = require('aws-sdk');
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const s3 = new AWS.S3({
    endpoint: process.env.AWS_ENDPOINT_URL || undefined
});

exports.handler = async (event) => {
    const bucketName = process.env.BUCKET_NAME;
    const repoUrl = event.repository_url;
    const targetPath = event.target_path || 'dist';
    const s3Prefix = event.s3_prefix || 'builds';

    const tmpDir = `/tmp/repo-${Date.now()}`;

    try {
        execSync(`git clone ${repoUrl} ${tmpDir}`, { stdio: 'pipe' });

        execSync('npm ci', { cwd: tmpDir, stdio: 'pipe' });

        execSync('npm run build', { cwd: tmpDir, stdio: 'pipe' });

        let buildDir = path.join(tmpDir, targetPath);
        if (!fs.existsSync(buildDir)) {
            const distDir = path.join(tmpDir, 'dist');
            if (fs.existsSync(distDir)) {
                buildDir = distDir;
            } else {
                throw new Error(`Build output not found at ${targetPath} or dist`);
            }
        }

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
        execSync(`rm -rf ${tmpDir}`, { stdio: 'pipe' }).catch(() => {});
        return {
            statusCode: 500,
            body: JSON.stringify({
                status: 'failed',
                error: error.message
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
            await s3.putObject({
                Bucket: bucket,
                Key: key,
                Body: fileContent
            }).promise();
            files.push(key);
        }
    }
    return files;
}