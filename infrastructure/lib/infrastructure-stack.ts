import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { ConfigHelper, EnvironmentConfig } from './config';
import { IamConstruct } from './iam-construct';
import { S3Construct } from './s3-construct';
import { LambdaConstruct } from './lambda-construct';
import { AnalyticsConstruct } from './analytics-construct';
import { CatalogConstruct } from './catalog-construct';

export interface CatalunyaDataStackProps extends cdk.StackProps {
  environmentName: string;
  projectName: string;
}

export class CatalunyaDataStack extends cdk.Stack {
  public readonly environmentName: string;
  public readonly projectName: string;
  public readonly config: EnvironmentConfig;

  public readonly bucketName: string;
  public readonly catalogBucketName: string;
  public readonly lambdaPrefix: string;
  public readonly athenaWorkgroupName: string;
  public readonly athenaDatabaseName: string;
  public readonly athenaResultsBucketName: string;

  // Construct references
  public readonly iamInfrastructure: IamConstruct;
  public readonly s3Infrastructure: S3Construct;
  public readonly lambdaInfrastructure: LambdaConstruct;
  public readonly analyticsInfrastructure: AnalyticsConstruct;
  public readonly catalogInfrastructure: CatalogConstruct;

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
    this.catalogBucketName = this.config.catalogBucketName

    // Apply common tags to the entire stack
    const commonTags = ConfigHelper.getCommonTags(this.environmentName);
    Object.entries(commonTags).forEach(([key, value]) => {
      cdk.Tags.of(this).add(key, value);
    });

    // ========================================
    // IAM Infrastructure (Security Layer) - FIRST!
    // ========================================
    this.iamInfrastructure = new IamConstruct(this, 'IamInfrastructure', {
      environmentName: this.environmentName,
      projectName: this.projectName,
      config: this.config,
      account: this.account,
      region: this.region,
      bucketName: this.bucketName,
      athenaResultsBucketName: this.athenaResultsBucketName,
      athenaDatabaseName: this.athenaDatabaseName,
      athenaWorkgroupName: this.athenaWorkgroupName,
      catalogBucketName: this.catalogBucketName,
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
      extractorExecutionRole: this.iamInfrastructure.extractorExecutionRole,
      transformerExecutionRole: this.iamInfrastructure.transformerExecutionRole,
      martExecutionRole: this.iamInfrastructure.martExecutionRole,
      monitoringExecutionRole: this.iamInfrastructure.monitoringExecutionRole,
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
    // Catalog Infrastructure (Dimension Tables Layer)
    // ========================================
    this.catalogInfrastructure = new CatalogConstruct(this, 'CatalogInfrastructure', {
      environmentName: this.environmentName,
      projectName: this.projectName,
      config: this.config,
      dataBucketName: this.bucketName,
      athenaDatabaseName: this.athenaDatabaseName,
      lambdaPrefix: this.lambdaPrefix,
      account: this.account,
      region: this.region,
      // Pass IAM roles for catalog functions if needed
      catalogExecutorRole: this.iamInfrastructure.catalogExecutorRole, // Catalog functions can use extractor role
    });

    // ========================================
    // Cross-Construct Dependencies
    // ========================================

    // S3 depends on IAM (for bucket policies if needed)
    this.s3Infrastructure.node.addDependency(this.iamInfrastructure);

    // Lambda depends on both IAM and S3
    this.lambdaInfrastructure.node.addDependency(this.iamInfrastructure);
    this.lambdaInfrastructure.node.addDependency(this.s3Infrastructure);

    // Analytics depends on IAM and S3
    this.analyticsInfrastructure.node.addDependency(this.iamInfrastructure);
    this.analyticsInfrastructure.node.addDependency(this.s3Infrastructure);

    // Catalog depends on all previous layers
    this.catalogInfrastructure.node.addDependency(this.iamInfrastructure);
    this.catalogInfrastructure.node.addDependency(this.s3Infrastructure);
    this.catalogInfrastructure.node.addDependency(this.analyticsInfrastructure);

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

    // IAM Role Outputs
    new cdk.CfnOutput(this, 'ExtractorRoleArn', {
      value: this.iamInfrastructure.extractorExecutionRole.roleArn,
      description: 'Lambda extractor execution role ARN',
      exportName: `${this.projectName}-ExtractorRoleArn`,
    });

    new cdk.CfnOutput(this, 'TransformerRoleArn', {
      value: this.iamInfrastructure.transformerExecutionRole.roleArn,
      description: 'Lambda transformer execution role ARN',
      exportName: `${this.projectName}-TransformerRoleArn`,
    });

    new cdk.CfnOutput(this, 'MartRoleArn', {
      value: this.iamInfrastructure.martExecutionRole.roleArn,
      description: 'Mart execution role ARN',
      exportName: `${this.projectName}-MartRoleArn`,
    });

    new cdk.CfnOutput(this, 'DataEngineerRoleArn', {
      value: this.iamInfrastructure.dataEngineerRole.roleArn,
      description: 'Data engineer human role ARN',
      exportName: `${this.projectName}-DataEngineerRoleArn`,
    });

    new cdk.CfnOutput(this, 'CatalogExecutorRoleArn', {
      value: this.iamInfrastructure.catalogExecutorRole.roleArn,
      description: 'Catalog executor role ARN',
      exportName: `${this.projectName}-CatalogExecutorRoleArn`,
    });

    new cdk.CfnOutput(this, 'AirflowCrossAccountRoleArn', {
      value: this.iamInfrastructure.airflowCrossAccountRole.roleArn,
      description: 'Airflow cross-account role ARN',
      exportName: `${this.projectName}-AirflowCrossAccountRoleArn`,
    });

    // Airflow Authentication Outputs (Minimal Assumer User)
    new cdk.CfnOutput(this, 'AirflowAssumerUserName', {
      value: this.iamInfrastructure.airflowUser.userName,
      description: 'Airflow assumer IAM user name (minimal permissions - only AssumeRole)',
      exportName: `${this.projectName}-AirflowAssumerUserName`,
    });

    new cdk.CfnOutput(this, 'AirflowAssumerAccessKeyId', {
      value: this.iamInfrastructure.airflowAccessKey.accessKeyId,
      description: 'Airflow assumer access key ID (SENSITIVE - only for AssumeRole)',
      exportName: `${this.projectName}-AirflowAssumerAccessKeyId`,
    });

    new cdk.CfnOutput(this, 'AirflowAssumerSecretAccessKey', {
      value: this.iamInfrastructure.airflowAccessKey.secretAccessKey.unsafeUnwrap(),
      description: 'Airflow assumer secret access key (VERY SENSITIVE - only for AssumeRole)',
      exportName: `${this.projectName}-AirflowAssumerSecretAccessKey`,
    });

    new cdk.CfnOutput(this, 'AirflowTargetRoleArn', {
      value: this.iamInfrastructure.airflowCrossAccountRole.roleArn,
      description: 'Airflow target role ARN (role to assume for Lambda permissions)',
      exportName: `${this.projectName}-AirflowTargetRoleArn`,
    });

    new cdk.CfnOutput(this, 'AirflowExternalId', {
      value: `catalunya-${this.environmentName}-airflow-exec`,
      description: 'External ID required for AssumeRole (additional security)',
      exportName: `${this.projectName}-AirflowExternalId`,
    });

    // Note: GitHub deployment role ARN output removed as it's now managed by setup scripts
    // The role ARN can be retrieved via AWS CLI if needed:
    // aws iam get-role --role-name catalunya-deployment-role-${environmentName} --query 'Role.Arn'
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

  /**
   * Access to the catalog bucket
   */
  public get catalogBucket() {
    return this.catalogInfrastructure.catalogBucket;
  }

  /**
   * Access to the catalog initializer Lambda function
   */
  public get serviceTypeCatalogLambda() {
    return this.catalogInfrastructure.serviceTypeCatalogLambda;
  }

  public get municipalsCatalogLambda() {
    return this.catalogInfrastructure.municipalsCatalogLambda;
  }

  // ========================================
  // IAM Accessors
  // ========================================

  /**
   * Access to IAM roles
   */
  public get extractorExecutionRole() {
    return this.iamInfrastructure.extractorExecutionRole;
  }

  public get transformerExecutionRole() {
    return this.iamInfrastructure.transformerExecutionRole;
  }

  public get martExecutionRole() {
    return this.iamInfrastructure.martExecutionRole;
  }

  public get monitoringExecutionRole() {
    return this.iamInfrastructure.monitoringExecutionRole;
  }

  public get dataEngineerRole() {
    return this.iamInfrastructure.dataEngineerRole;
  }

  public get catalogExecutorRole() {
    return this.iamInfrastructure.catalogExecutorRole;
  }

  public get airflowCrossAccountRole() {
    return this.iamInfrastructure.airflowCrossAccountRole;
  }

  public get airflowUser() {
    return this.iamInfrastructure.airflowUser;
  }

  public get airflowAccessKey() {
    return this.iamInfrastructure.airflowAccessKey;
  }

  /**
   * Get a Lambda execution role by service type
   */
  public getLambdaExecutionRole(serviceType: 'extractor' | 'transformer' | 'mart' | 'monitoring') {
    return this.iamInfrastructure.getLambdaExecutionRole(serviceType);
  }
}