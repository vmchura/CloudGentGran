#!/bin/bash

export BUCKET_NAME="catalunya-data-dev"
export REPOSITORY_URL='https://github.com/vmchura/CloudGentGran'
export ENVIRONMENT="develop"
export REGION='eu-west-1'
export IS_LOCAL=true
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

node index.js