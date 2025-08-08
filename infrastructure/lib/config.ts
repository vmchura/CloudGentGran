import { Construct } from 'constructs';

export interface EnvironmentConfig {
  region: string;
  bucketName: string;
  lambdaMemory: number;
  lambdaTimeout: number;
  retentionPeriod: number;
  scheduleCron: string;
}

export class ConfigHelper {
  public static getEnvironmentConfig(scope: Construct, environmentName: string): EnvironmentConfig {
    const projectConfig = scope.node.tryGetContext('Catalunya-Data-Pipeline');
    
    if (!projectConfig) {
      throw new Error(`No 'Catalunya-Data-Pipeline' configuration found in cdk.json`);
    }
    
    const config = projectConfig[environmentName];
    
    if (!config) {
      throw new Error(`No configuration found for environment: ${environmentName}. Available environments: ${Object.keys(projectConfig).join(', ')}`);
    }

    return {
      region: config.region || 'eu-west-1',
      bucketName: config.bucketName || `catalunya-data-${environmentName}`,
      lambdaMemory: config.lambdaMemory || 512,
      lambdaTimeout: config.lambdaTimeout || 300,
      retentionPeriod: config.retentionPeriod || 30,
      scheduleCron: config.scheduleCron || 'cron(0 23 ? * fri *)',
    };
  }

  public static validateEnvironment(environmentName: string): void {
    const validEnvironments = ['dev', 'prod'];
    if (!validEnvironments.includes(environmentName)) {
      throw new Error(`Invalid environment: ${environmentName}. Valid environments are: ${validEnvironments.join(', ')}`);
    }
  }

  public static getResourceName(baseName: string, environmentName: string): string {
    return `${baseName}-${environmentName}`;
  }

  public static getCommonTags(environmentName: string): Record<string, string> {
    return {
      Project: 'CatalunyaDataPipeline',
      Environment: environmentName,
      Owner: 'CloudGentGran',
      ManagedBy: 'AWS-CDK',
    };
  }
}
