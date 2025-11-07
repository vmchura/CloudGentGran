#!/bin/bash

REPO_PATH=${1:-"/path/to/your/observable/project"}
BUCKET_NAME=${2:-"test-bucket"}

export BUCKET_NAME=$BUCKET_NAME
export IS_LOCAL=true
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

node index.js "$REPO_PATH" "dist" "test-builds"