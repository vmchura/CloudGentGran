import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { CatalunyaDataStack } from '../lib/infrastructure-stack';

describe('Catalunya Data Stack', () => {
  let app: cdk.App;

  beforeEach(() => {
    app = new cdk.App({
      context: {
        'Catalunya-Data-Pipeline': {
          'dev': {
            region: 'eu-west-1',
            bucketName: 'catalunya-data-dev',
            lambdaMemory: 512,
            lambdaTimeout: 300,
            retentionPeriod: 30,
            scheduleCron: 'cron(0 6 * * ? *)'
          },
          'prod': {
            region: 'eu-west-1',
            bucketName: 'catalunya-data-prod',
            lambdaMemory: 1024,
            lambdaTimeout: 900,
            retentionPeriod: 90,
            scheduleCron: 'cron(0 5 * * ? *)'
          }
        }
      }
    });
  });

  test('Development stack synthesizes correctly', () => {
    // WHEN
    const stack = new CatalunyaDataStack(app, 'TestDevStack', {
      environmentName: 'dev',
      projectName: 'test-catalunya-dev',
      description: 'Test development stack',
    });

    // THEN
    const template = Template.fromStack(stack);

    // Verify that the stack has outputs (basic validation)
    expect(template.toJSON().Outputs).toBeDefined();
    expect(Object.keys(template.toJSON().Outputs || {}).length).toBeGreaterThan(0);
  });

  test('Production stack synthesizes correctly', () => {
    // WHEN
    const stack = new CatalunyaDataStack(app, 'TestProdStack', {
      environmentName: 'prod',
      projectName: 'test-catalunya-prod',
      description: 'Test production stack',
    });

    // THEN
    const template = Template.fromStack(stack);

    // Verify that the stack has outputs (basic validation)
    expect(template.toJSON().Outputs).toBeDefined();
    expect(Object.keys(template.toJSON().Outputs || {}).length).toBeGreaterThan(0);
  });

  test('Stack has correct outputs', () => {
    // WHEN
    const stack = new CatalunyaDataStack(app, 'TestStack', {
      environmentName: 'dev',
      projectName: 'test-catalunya-dev',
      description: 'Test stack',
    });

    // THEN
    const template = Template.fromStack(stack);

    // Verify outputs exist
    template.hasOutput('Environment', {
      Value: 'dev',
      Export: { Name: 'test-catalunya-dev-Environment' }
    });

    template.hasOutput('BucketName', {
      Value: 'catalunya-data-dev',
      Export: { Name: 'test-catalunya-dev-BucketName' }
    });

    template.hasOutput('AthenaWorkgroup', {
      Value: 'catalunya-workgroup-dev',
      Export: { Name: 'test-catalunya-dev-AthenaWorkgroup' }
    });

    template.hasOutput('AthenaDatabase', {
      Value: 'catalunya_data_dev',
      Export: { Name: 'test-catalunya-dev-AthenaDatabase' }
    });

    template.hasOutput('LambdaPrefix', {
      Value: 'catalunya-dev',
      Export: { Name: 'test-catalunya-dev-LambdaPrefix' }
    });
  });

  test('Invalid environment throws error', () => {
    // WHEN & THEN
    expect(() => {
      new CatalunyaDataStack(app, 'TestInvalidStack', {
        environmentName: 'invalid',
        projectName: 'test-catalunya-invalid',
        description: 'Test invalid stack',
      });
    }).toThrow('Invalid environment: invalid');
  });
});
