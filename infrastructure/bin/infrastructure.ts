#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { CatalunyaDataStack } from '../lib/infrastructure-stack';

const app = new cdk.App();

// Environment configurations
const devEnv = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION || 'eu-west-1',
};

const prodEnv = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION || 'eu-west-1',
};

// Deploy development stack
const devStack = new CatalunyaDataStack(app, 'CatalunyaDataStack-dev', {
  env: devEnv,
  environmentName: 'dev',
  projectName: 'catalunya-data-dev',
  description: 'Catalunya Open Data Pipeline - Development Environment',
});

// Deploy production stack
const prodStack = new CatalunyaDataStack(app, 'CatalunyaDataStack-prod', {
  env: prodEnv,
  environmentName: 'prod',
  projectName: 'catalunya-data-prod',
  description: 'Catalunya Open Data Pipeline - Production Environment',
});
