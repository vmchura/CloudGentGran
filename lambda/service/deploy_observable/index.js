const AWS = require('aws-sdk');
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const isLocalStack = process.env.IS_LOCAL === 'true';

const s3 = new AWS.S3({
    endpoint: process.env.AWS_ENDPOINT_URL || undefined,
    s3ForcePathStyle: true
});

exports.handler = async (event) => {
    const bucketName = process.env.BUCKET_NAME;
    const repoUrl = event.repository_url;
    const targetPath = event.target_path || 'dist';
    const s3Prefix = event.s3_prefix || 'builds';
    const localRepoPath = event.local_repo_path;

    const tmpDir = `/tmp/repo-${Date.now()}`;

    try {
        if (isLocalStack) {
            console.log(`LocalStack mode: using local repo at ${localRepoPath}`);
            execSync(`cp -r ${localRepoPath} ${tmpDir}`, { stdio: 'inherit' });
        } else {
            console.log(`Cloning ${repoUrl}...`);
            execSync(`git clone ${repoUrl} ${tmpDir}`, { stdio: 'inherit' });
        }

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

if (require.main === module) {
    const testEvent = {
        local_repo_path: process.argv[2] || process.env.TEST_REPO_PATH,
        target_path: process.argv[3] || 'dist',
        s3_prefix: process.argv[4] || 'test-builds'
    };

    process.env.BUCKET_NAME = process.env.BUCKET_NAME || 'test-bucket';
    process.env.IS_LOCAL = 'true';
    process.env.AWS_ENDPOINT_URL = process.env.AWS_ENDPOINT_URL || 'http://localhost:4566';

    console.log('Testing with event:', testEvent);
    exports.handler(testEvent).then(result => {
        console.log('Result:', JSON.stringify(result, null, 2));
        process.exit(result.statusCode === 200 ? 0 : 1);
    }).catch(err => {
        console.error('Fatal error:', err);
        process.exit(1);
    });
}