import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as glue from 'aws-cdk-lib/aws-glue';
import * as athena from 'aws-cdk-lib/aws-athena';
import { Construct } from 'constructs';
import { ConfigHelper, EnvironmentConfig } from './config';

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
  
  // S3 Resources
  public readonly dataBucket: s3.Bucket;
  public readonly athenaResultsBucket: s3.Bucket;
  
  // Glue Resources
  public readonly glueDatabase: glue.CfnDatabase;
  
  // Athena Resources  
  public readonly athenaWorkgroup: athena.CfnWorkGroup;
  
  // Lambda Resources
  public apiExtractorLambda: lambda.Function;
  public socialServicesTransformerLambda: lambda.Function;
  
  constructor(scope: Construct, id: string, props: CatalunyaDataStackProps) {
    super(scope, id, props);

    ConfigHelper.validateEnvironment(props.environmentName);

    this.environmentName = props.environmentName;
    this.projectName = props.projectName;
    
    this.config = ConfigHelper.getEnvironmentConfig(this, this.environmentName);
    
    this.bucketName = this.config.bucketName;
    this.lambdaPrefix = ConfigHelper.getResourceName('catalunya', this.environmentName);
    this.athenaWorkgroupName = ConfigHelper.getResourceName('catalunya-workgroup', this.environmentName);
    this.athenaDatabaseName = `catalunya_data_${this.environmentName}`;
    this.athenaResultsBucketName = ConfigHelper.getResourceName('catalunya-athena-results', this.environmentName);

    const commonTags = ConfigHelper.getCommonTags(this.environmentName);
    Object.entries(commonTags).forEach(([key, value]) => {
      cdk.Tags.of(this).add(key, value);
    });

    // ========================================
    // S3 Infrastructure
    // ========================================
    this.createS3Infrastructure();

    // ========================================
    // Glue Data Catalog Infrastructure
    // ========================================
    this.createGlueDataCatalog();

    // ========================================
    // Athena Infrastructure
    // ========================================
    this.createAthenaInfrastructure();

    // ========================================
    // Lambda Infrastructure
    // ========================================
    this.createLambdaInfrastructure();

    // ========================================
    // Transformer Infrastructure
    // ========================================
    this.createTransformerInfrastructure();

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

    new cdk.CfnOutput(this, 'AthenaWorkgroupConfig', {
      value: this.athenaWorkgroupName,
      description: 'Athena workgroup name',
      exportName: `${this.projectName}-AthenaWorkgroup`,
    });

    new cdk.CfnOutput(this, 'AthenaDatabase', {
      value: this.athenaDatabaseName,
      description: 'Athena database name',
      exportName: `${this.projectName}-AthenaDatabase`,
    });

    new cdk.CfnOutput(this, 'AthenaResultsBucketConfig', {
      value: this.athenaResultsBucketName,
      description: 'S3 bucket name for Athena query results',
      exportName: `${this.projectName}-AthenaResultsBucket`,
    });

    new cdk.CfnOutput(this, 'LambdaPrefix', {
      value: this.lambdaPrefix,
      description: 'Lambda function prefix',
      exportName: `${this.projectName}-LambdaPrefix`,
    });

    this.templateOptions.description = props.description;

    new cdk.CfnOutput(this, 'Region', {
      value: this.region,
      description: 'AWS region where resources are deployed',
      exportName: `${this.projectName}-Region`,
    });
  }

  /**
   * Gets the appropriate Python Lambda code, skipping bundling for tests
   */
  private getPythonLambdaCode(): lambda.Code {
    const isTest = process.env.NODE_ENV === 'test' || 
                   process.env.CDK_DEFAULT_ACCOUNT === '123456789012';

    if (isTest) {
      // Skip bundling for tests - just use the source directory
      console.log('🧪 Skipping Python bundling for tests');
      return lambda.Code.fromAsset('../lambda/extractors/social_services');
    } else {
      // Use bundling for real deployments
      console.log('📦 Using Python bundling for deployment');
      return lambda.Code.fromAsset('../lambda/extractors/social_services', {
        bundling: {
          image: lambda.Runtime.PYTHON_3_9.bundlingImage,
          command: [
            'bash', '-c', [
              'pip install -r requirements.txt -t /asset-output',
              'cp -au . /asset-output'
            ].join(' && ')
          ],
        },
      });
    }
  }

  /**
   * Creates S3 infrastructure including main data bucket with folder structure,
   * lifecycle policies, encryption, and CORS configuration, plus dedicated Athena results bucket
   */
  private createS3Infrastructure(): void {
    // Define lifecycle rules for cost optimization
    const lifecycleRules: s3.LifecycleRule[] = [
      {
          id: 'LandingLayerExpiration',
          prefix: 'landing/',
          enabled: true,
          expiration: cdk.Duration.days(7),
      },
      {
        id: 'StagingLayerTransition',
        prefix: 'staging/',
        enabled: true,
        transitions: [
          {
            storageClass: s3.StorageClass.INFREQUENT_ACCESS,
            transitionAfter: cdk.Duration.days(60),
          },
        ],
      },
      {
        id: 'MartsLayerRetention',
        prefix: 'marts/',
        enabled: true,
        transitions: [
          {
            storageClass: s3.StorageClass.INFREQUENT_ACCESS,
            transitionAfter: cdk.Duration.days(60),
          },
        ],
      },
      {
        id: 'AthenaResultsCleanup',
        prefix: 'athena-results/',
        enabled: true,
        expiration: cdk.Duration.days(this.config.retentionPeriod),
      },
    ];

    // Create the main data bucket
    const dataBucket = new s3.Bucket(this, 'DataBucket', {
      bucketName: this.bucketName,

      publicReadAccess: false,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      
      // Versioning for data protection
      versioned: this.environmentName === 'prod',
      
      // Lifecycle rules for cost optimization
      lifecycleRules: lifecycleRules,
      
      // CORS configuration for potential web access
      cors: [
        {
          allowedMethods: [s3.HttpMethods.GET, s3.HttpMethods.HEAD],
          allowedOrigins: ['*'],
          allowedHeaders: ['*'],
          maxAge: 3600,
        },
      ],
      
      // Deletion protection
      removalPolicy: this.environmentName === 'prod' 
        ? cdk.RemovalPolicy.RETAIN 
        : cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: this.environmentName !== 'prod',
    });

    // Create dedicated Athena results bucket
    const athenaResultsBucket = new s3.Bucket(this, 'AthenaResultsBucket', {
      bucketName: this.athenaResultsBucketName,

      publicReadAccess: false,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      
      // Versioning not needed for query results
      versioned: false,
      
      // Lifecycle rules for query result cleanup
      lifecycleRules: [
        {
          id: 'QueryResultsCleanup',
          enabled: true,
          expiration: cdk.Duration.days(30), // Keep results for 30 days
          abortIncompleteMultipartUploadAfter: cdk.Duration.days(1),
        },
      ],
      
      // Deletion protection
      removalPolicy: this.environmentName === 'prod' 
        ? cdk.RemovalPolicy.RETAIN 
        : cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: this.environmentName !== 'prod',
    });

    // Store references for other resources
    (this as any).dataBucket = dataBucket;
    (this as any).athenaResultsBucket = athenaResultsBucket;

    // Tag the buckets
    const commonTags = ConfigHelper.getCommonTags(this.environmentName);
    
    [dataBucket, athenaResultsBucket].forEach(bucket => {
      Object.entries(commonTags).forEach(([key, value]) => {
        cdk.Tags.of(bucket).add(key, value);
      });
    });

    // Additional S3 bucket tags
    cdk.Tags.of(dataBucket).add('Purpose', 'DataLake');
    cdk.Tags.of(dataBucket).add('Layer', 'Storage');
    cdk.Tags.of(dataBucket).add('DataClassification', 'OpenData');

    cdk.Tags.of(athenaResultsBucket).add('Purpose', 'QueryResults');
    cdk.Tags.of(athenaResultsBucket).add('Layer', 'Analytics');
    cdk.Tags.of(athenaResultsBucket).add('DataClassification', 'Processed');

    // Output bucket information
    new cdk.CfnOutput(this, 'S3BucketArn', {
      value: dataBucket.bucketArn,
      description: 'ARN of the main data S3 bucket',
      exportName: `${this.projectName}-S3BucketArn`,
    });

    new cdk.CfnOutput(this, 'S3BucketDomainName', {
      value: dataBucket.bucketDomainName,
      description: 'Domain name of the main data S3 bucket',
      exportName: `${this.projectName}-S3BucketDomainName`,
    });

    new cdk.CfnOutput(this, 'AthenaResultsBucketArn', {
      value: athenaResultsBucket.bucketArn,
      description: 'ARN of the Athena results S3 bucket',
      exportName: `${this.projectName}-AthenaResultsBucketArn`,
    });
  }

  /**
   * Creates Lambda infrastructure including the API extractor function with proper IAM roles and EventBridge scheduling
   */
  private createLambdaInfrastructure(): void {
    // ========================================
    // IAM Role for Lambda
    // ========================================
    
    // Use existing IAM role or create inline permissions
    const lambdaRole = iam.Role.fromRoleArn(
      this,
      'ApiExtractorRole',
      `arn:aws:iam::${this.account}:role/catalunya-lambda-extractor-role-${this.environmentName}`
    );

    // ========================================
    // Lambda Function
    // ========================================
    
    this.apiExtractorLambda = new lambda.Function(this, 'social_services_ApiExtractorLambda', {
      functionName: `${this.lambdaPrefix}-social_services`,
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: 'api_extractor.lambda_handler',
      code: this.getPythonLambdaCode(),
      timeout: cdk.Duration.seconds(this.config.lambdaTimeout),
      memorySize: this.config.lambdaMemory,
      role: lambdaRole,
      environment: {
        BUCKET_NAME: this.bucketName,
        SEMANTIC_IDENTIFIER: 'social_services',
        DATASET_IDENTIFIER: 'ivft-vegh',
        ENVIRONMENT: this.environmentName,
        REGION: this.region
      },
      description: `API Extractor Lambda for ${this.environmentName} environment`,
    });

    // ========================================
    // EventBridge Rule for Scheduling
    // ========================================
    
    const extractorScheduleRule = new events.Rule(this, 'ApiExtractorSchedule', {
      ruleName: `${this.lambdaPrefix}-api-extractor-schedule`,
      description: `Scheduled trigger for API extractor Lambda in ${this.environmentName}`,
      schedule: events.Schedule.expression(this.config.scheduleCron),
      enabled: true,
    });

    // Add Lambda as target
    extractorScheduleRule.addTarget(new targets.LambdaFunction(this.apiExtractorLambda, {
      event: events.RuleTargetInput.fromObject({
        source: 'eventbridge.schedule',
        environment: this.environmentName,
        trigger_time: events.EventField.fromPath('$.time')
      })
    }));

    // ========================================
    // Tags and Outputs
    // ========================================
    
    const commonTags = ConfigHelper.getCommonTags(this.environmentName);
    Object.entries(commonTags).forEach(([key, value]) => {
      cdk.Tags.of(this.apiExtractorLambda).add(key, value);
      cdk.Tags.of(extractorScheduleRule).add(key, value);
    });

    // Additional Lambda tags
    cdk.Tags.of(this.apiExtractorLambda).add('Purpose', 'DataExtraction');
    cdk.Tags.of(this.apiExtractorLambda).add('Layer', 'Ingestion');
    cdk.Tags.of(this.apiExtractorLambda).add('DataSource', 'PublicAPI');

    // Lambda outputs
    new cdk.CfnOutput(this, 'ApiExtractorLambdaArn', {
      value: this.apiExtractorLambda.functionArn,
      description: 'ARN of the API Extractor Lambda function',
      exportName: `${this.projectName}-ApiExtractorLambdaArn`,
    });

    new cdk.CfnOutput(this, 'ApiExtractorLambdaName', {
      value: this.apiExtractorLambda.functionName,
      description: 'Name of the API Extractor Lambda function',
      exportName: `${this.projectName}-ApiExtractorLambdaName`,
    });

    new cdk.CfnOutput(this, 'ApiExtractorScheduleArn', {
      value: extractorScheduleRule.ruleArn,
      description: 'ARN of the API Extractor EventBridge schedule rule',
      exportName: `${this.projectName}-ApiExtractorScheduleArn`,
    });
  }

  /**
   * Creates Transformer Lambda infrastructure including the social services transformer function 
   * with EventBridge event triggers and proper IAM roles
   */
  private createTransformerInfrastructure(): void {
    // ========================================
    // IAM Role for Transformer Lambda
    // ========================================
    
    const transformerRole = iam.Role.fromRoleArn(
      this,
      'TransformerRole',
      `arn:aws:iam::${this.account}:role/catalunya-lambda-transformer-role-${this.environmentName}`
    );

    // ========================================
    // Social Services Transformer Lambda (Rust)
    // ========================================
    
    this.socialServicesTransformerLambda = new lambda.Function(this, 'SocialServicesTransformerLambda', {
      functionName: `${this.lambdaPrefix}-social-services-transformer`,
      runtime: lambda.Runtime.PROVIDED_AL2023,
      handler: 'bootstrap',
      code: lambda.Code.fromAsset('../rust-lambda-build'),
      timeout: cdk.Duration.seconds(this.config.lambdaTimeout),
      memorySize: this.config.lambdaMemory,
      role: transformerRole,
      environment: {
        BUCKET_NAME: this.bucketName,
        SEMANTIC_IDENTIFIER: 'social_services',
        ENVIRONMENT: this.environmentName,
        REGION: this.region
      },
      description: `Social Services Transformer Lambda (Rust) for ${this.environmentName} environment`,
    });

    // ========================================
    // EventBridge Rule for Data Download Complete Events
    // ========================================
    
    const transformerEventRule = new events.Rule(this, 'TransformerEventRule', {
      ruleName: `${this.lambdaPrefix}-transformer-trigger`,
      description: `EventBridge rule to trigger transformer when API extraction completes`,
      eventPattern: {
        source: ['social-services-api-extractor'],
        detailType: ['Data Download Complete'],
        detail: {
          semantic_identifier: ['social_services']
        }
      },
      enabled: true,
    });

    // Add Transformer Lambda as target
    transformerEventRule.addTarget(new targets.LambdaFunction(this.socialServicesTransformerLambda, {
      event: events.RuleTargetInput.fromObject({
        source: 'eventbridge.data-download-complete',
        detail: events.EventField.fromPath('$.detail'),
        environment: this.environmentName,
        trigger_time: events.EventField.fromPath('$.time')
      })
    }));

    // ========================================
    // Tags and Outputs
    // ========================================
    
    const commonTags = ConfigHelper.getCommonTags(this.environmentName);
    Object.entries(commonTags).forEach(([key, value]) => {
      cdk.Tags.of(this.socialServicesTransformerLambda).add(key, value);
      cdk.Tags.of(transformerEventRule).add(key, value);
    });

    // Additional transformer tags
    cdk.Tags.of(this.socialServicesTransformerLambda).add('Purpose', 'DataTransformation');
    cdk.Tags.of(this.socialServicesTransformerLambda).add('Layer', 'Processing');
    cdk.Tags.of(this.socialServicesTransformerLambda).add('DataFlow', 'LandingToStaging');

    // Transformer outputs
    new cdk.CfnOutput(this, 'SocialServicesTransformerLambdaArn', {
      value: this.socialServicesTransformerLambda.functionArn,
      description: 'ARN of the Social Services Transformer Lambda function',
      exportName: `${this.projectName}-SocialServicesTransformerLambdaArn`,
    });

    new cdk.CfnOutput(this, 'SocialServicesTransformerLambdaName', {
      value: this.socialServicesTransformerLambda.functionName,
      description: 'Name of the Social Services Transformer Lambda function',
      exportName: `${this.projectName}-SocialServicesTransformerLambdaName`,
    });

    new cdk.CfnOutput(this, 'TransformerEventRuleArn', {
      value: transformerEventRule.ruleArn,
      description: 'ARN of the EventBridge rule that triggers the transformer',
      exportName: `${this.projectName}-TransformerEventRuleArn`,
    });
  }

  /**
   * Creates AWS Glue Data Catalog database for storing table metadata
   */
  private createGlueDataCatalog(): void {
    // ========================================
    // Glue Database
    // ========================================
    
    const glueDatabase = new glue.CfnDatabase(this, 'GlueDatabase', {
      catalogId: this.account,
      databaseInput: {
        name: this.athenaDatabaseName,
        description: `Catalunya data catalog for ${this.environmentName} environment`,
        parameters: {
          'classification': 'parquet',
          'typeOfData': 'file',
          'creator': 'Catalunya Data Pipeline',
          'environment': this.environmentName,
        },
      },
    });

    // Store reference for other resources
    (this as any).glueDatabase = glueDatabase;

    // Tag the database
    const commonTags = ConfigHelper.getCommonTags(this.environmentName);
    Object.entries(commonTags).forEach(([key, value]) => {
      cdk.Tags.of(glueDatabase).add(key, value);
    });

    // Additional Glue database tags
    cdk.Tags.of(glueDatabase).add('Purpose', 'DataCatalog');
    cdk.Tags.of(glueDatabase).add('Layer', 'Metadata');
    cdk.Tags.of(glueDatabase).add('DataFormat', 'Parquet');

    // Output database information
    new cdk.CfnOutput(this, 'GlueDatabaseName', {
      value: glueDatabase.ref,
      description: 'Name of the Glue Data Catalog database',
      exportName: `${this.projectName}-GlueDatabaseName`,
    });
  }

  /**
   * Creates Athena workgroup with query result location and cost controls
   */
  private createAthenaInfrastructure(): void {
    // ========================================
    // Athena Workgroup
    // ========================================
    
    const workgroupConfiguration: athena.CfnWorkGroup.WorkGroupConfigurationProperty = {
      resultConfiguration: {
        outputLocation: `s3://${this.athenaResultsBucketName}/query-results/`,
        encryptionConfiguration: {
          encryptionOption: 'SSE_S3',
        },
      },
      enforceWorkGroupConfiguration: true,
      publishCloudWatchMetricsEnabled: true,
      bytesScannedCutoffPerQuery: this.environmentName === 'prod' 
        ? 10 * 1024 * 1024 * 1024 // 10GB limit for prod
        : 1 * 1024 * 1024 * 1024,  // 1GB limit for dev
      requesterPaysEnabled: false,
    };

    const athenaWorkgroup = new athena.CfnWorkGroup(this, 'AthenaWorkgroup', {
      name: this.athenaWorkgroupName,
      description: `Athena workgroup for Catalunya data pipeline - ${this.environmentName} environment`,
      state: 'ENABLED',
      workGroupConfiguration: workgroupConfiguration,
      tags: [
        {
          key: 'Environment',
          value: this.environmentName,
        },
        {
          key: 'Project',
          value: this.projectName,
        },
        {
          key: 'Purpose',
          value: 'DataAnalytics',
        },
        {
          key: 'Layer',
          value: 'QueryEngine',
        },
      ],
    });

    // Add dependency on results bucket
    athenaWorkgroup.addDependency(this.athenaResultsBucket.node.defaultChild as cdk.CfnResource);

    // Store reference for other resources
    (this as any).athenaWorkgroup = athenaWorkgroup;

    // Output workgroup information
    new cdk.CfnOutput(this, 'AthenaWorkgroupName', {
      value: athenaWorkgroup.name || this.athenaWorkgroupName,
      description: 'Name of the Athena workgroup',
      exportName: `${this.projectName}-AthenaWorkgroupName`,
    });
  }
}
