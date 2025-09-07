import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { ConfigHelper, EnvironmentConfig } from './config';
import { S3Construct } from './s3-construct';
import { LambdaConstruct } from './lambda-construct';
import { AnalyticsConstruct } from './analytics-construct';

export interface CatalunyaDataStackProps extends cdk.StackProps {
  environmentName: string;
  projectName: string;
}

export class CatalunyaDataStack extends cdk.Stack {
  public readonly environmentName: string;
  public readonly projectName: string;
  public readonly config: EnvironmentConfig;

  public readonly bucketName: string;
  public readonly lambdaPrefix: string;
  public readonly athenaWorkgroupName: string;
  public readonly athenaDatabaseName: string;
  public readonly athenaResultsBucketName: string;

  // Construct references
  public readonly s3Infrastructure: S3Construct;
  public readonly lambdaInfrastructure: LambdaConstruct;
  public readonly analyticsInfrastructure: AnalyticsConstruct;

  constructor(scope: Construct, id: string, props: CatalunyaDataStackProps) {
    super(scope, id, props);

    ConfigHelper.validateEnvironment(props.environmentName);

    // ========================================
    // Configuration Setup
    // ========================================
    this.environmentName = props.environmentName;
    this.projectName = props.projectName;

    this.config = ConfigHelper.getEnvironmentConfig(this, this.environmentName);

    this.bucketName = this.config.bucketName;
    this.lambdaPrefix = ConfigHelper.getResourceName('catalunya', this.environmentName);
    this.athenaWorkgroupName = ConfigHelper.getResourceName('catalunya-workgroup', this.environmentName);
    this.athenaDatabaseName = `catalunya_data_${this.environmentName}`;
    this.athenaResultsBucketName = ConfigHelper.getResourceName('catalunya-athena-results', this.environmentName);

    // Apply common tags to the entire stack
    const commonTags = ConfigHelper.getCommonTags(this.environmentName);
    Object.entries(commonTags).forEach(([key, value]) => {
      cdk.Tags.of(this).add(key, value);
    });

    // ========================================
    // S3 Infrastructure (Storage Layer)
    // ========================================
    this.s3Infrastructure = new S3Construct(this, 'S3Infrastructure', {
      environmentName: this.environmentName,
      projectName: this.projectName,
      config: this.config,
      bucketName: this.bucketName,
      athenaResultsBucketName: this.athenaResultsBucketName,
    });

    // ========================================
    // Lambda Infrastructure (Processing Layer)
    // ========================================
    this.lambdaInfrastructure = new LambdaConstruct(this, 'LambdaInfrastructure', {
      environmentName: this.environmentName,
      projectName: this.projectName,
      config: this.config,
      bucketName: this.bucketName,
      lambdaPrefix: this.lambdaPrefix,
      account: this.account,
      region: this.region,
    });

    // ========================================
    // Analytics Infrastructure (Query Layer)
    // ========================================
    this.analyticsInfrastructure = new AnalyticsConstruct(this, 'AnalyticsInfrastructure', {
      environmentName: this.environmentName,
      projectName: this.projectName,
      config: this.config,
      account: this.account,
      athenaDatabaseName: this.athenaDatabaseName,
      athenaWorkgroupName: this.athenaWorkgroupName,
      athenaResultsBucketName: this.athenaResultsBucketName,
      athenaResultsBucket: this.s3Infrastructure.athenaResultsBucket,
    });

    // ========================================
    // Cross-Construct Dependencies
    // ========================================

    // Lambda depends on S3 buckets
    this.lambdaInfrastructure.node.addDependency(this.s3Infrastructure);

    // Analytics depends on both S3 and Lambda (for proper resource ordering)
    this.analyticsInfrastructure.node.addDependency(this.s3Infrastructure);
    this.analyticsInfrastructure.node.addDependency(this.lambdaInfrastructure);

    // ========================================
    // CloudFormation Outputs
    // ========================================
    this.createStackOutputs();

    // Set stack description
    this.templateOptions.description = props.description;
  }

  /**
   * Creates CloudFormation outputs for key stack resources
   */
  private createStackOutputs(): void {
    // Environment and configuration outputs
    new cdk.CfnOutput(this, 'Environment', {
      value: this.environmentName,
      description: 'Environment name (dev/prod)',
      exportName: `${this.projectName}-Environment`,
    });

    new cdk.CfnOutput(this, 'BucketName', {
      value: this.bucketName,
      description: 'S3 bucket name for data storage',
      exportName: `${this.projectName}-BucketName`,
    });

    new cdk.CfnOutput(this, 'AthenaWorkgroup', {
      value: this.athenaWorkgroupName,
      description: 'Athena workgroup name',
      exportName: `${this.projectName}-AthenaWorkgroup`,
    });

    new cdk.CfnOutput(this, 'AthenaDatabase', {
      value: this.athenaDatabaseName,
      description: 'Athena database name',
      exportName: `${this.projectName}-AthenaDatabase`,
    });

    new cdk.CfnOutput(this, 'AthenaResultsBucketName', {
      value: this.athenaResultsBucketName,
      description: 'S3 bucket name for Athena query results',
      exportName: `${this.projectName}-AthenaResultsBucket`,
    });

    new cdk.CfnOutput(this, 'LambdaPrefix', {
      value: this.lambdaPrefix,
      description: 'Lambda function prefix',
      exportName: `${this.projectName}-LambdaPrefix`,
    });

    new cdk.CfnOutput(this, 'Region', {
      value: this.region,
      description: 'AWS region where resources are deployed',
      exportName: `${this.projectName}-Region`,
    });
  }

  // ========================================
  // Public Accessors for Backward Compatibility
  // ========================================

  /**
   * Access to the main data bucket
   */
  public get dataBucket() {
    return this.s3Infrastructure.dataBucket;
  }

  /**
   * Access to the Athena results bucket
   */
  public get athenaResultsBucket() {
    return this.s3Infrastructure.athenaResultsBucket;
  }

  /**
   * Access to the Glue database
   */
  public get glueDatabase() {
    return this.analyticsInfrastructure.glueDatabase;
  }

  /**
   * Access to the Athena workgroup
   */
  public get athenaWorkgroup() {
    return this.analyticsInfrastructure.athenaWorkgroup;
  }

  /**
   * Access to the API extractor Lambda function
   */
  public get apiExtractorLambda() {
    return this.lambdaInfrastructure.apiExtractorLambda;
  }

  /**
   * Access to the social services transformer Lambda function
   */
  public get socialServicesTransformerLambda() {
    return this.lambdaInfrastructure.socialServicesTransformerLambda;
  }
}