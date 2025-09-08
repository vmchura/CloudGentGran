import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import { EnvironmentConfig, ConfigHelper } from './config';

export interface CatalogConstructProps {
  environmentName: string;
  projectName: string;
  config: EnvironmentConfig;
  dataBucketName: string;
  athenaDatabaseName: string;
  lambdaPrefix: string;
  account: string;
  region: string;
}

export class CatalogConstruct extends Construct {
  public readonly catalogBucket: s3.Bucket;
  public readonly catalogBucketName: string;
  public readonly catalogInitializerLambda: lambda.Function;

  constructor(scope: Construct, id: string, props: CatalogConstructProps) {
    super(scope, id);

    const {
      environmentName,
      projectName,
      config,
      lambdaPrefix,
      account,
      region
    } = props;

    // Generate catalog bucket name
    this.catalogBucketName = ConfigHelper.getResourceName('catalunya-catalog', environmentName);

    // Create simplified catalog infrastructure
    this.catalogBucket = this.createCatalogBucket(environmentName, projectName);
    this.catalogInitializerLambda = this.createSimpleCatalogLambda({
      environmentName,
      projectName,
      config,
      dataBucketName: props.dataBucketName,
      athenaDatabaseName: props.athenaDatabaseName,
      lambdaPrefix,
      account,
      region
    });
  }

  /**
   * Creates a simplified S3 bucket for storing raw parquet files
   */
  private createCatalogBucket(environmentName: string, projectName: string): s3.Bucket {
    const catalogBucket = new s3.Bucket(this, 'CatalogBucket', {
      bucketName: this.catalogBucketName,
      publicReadAccess: false,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,

      // Basic lifecycle rules for raw parquet files
      lifecycleRules: [
        {
          id: 'RawParquetRetention',
          prefix: 'raw_parquet/',
          enabled: true,
          transitions: [
            {
              storageClass: s3.StorageClass.INFREQUENT_ACCESS,
              transitionAfter: cdk.Duration.days(30),
            },
          ],
        },
        {
          id: 'TempFilesCleanup',
          prefix: 'temp/',
          enabled: true,
          expiration: cdk.Duration.days(7),
        },
      ],

      // Basic CORS for potential access
      cors: [
        {
          allowedMethods: [s3.HttpMethods.GET, s3.HttpMethods.HEAD],
          allowedOrigins: ['*'],
          allowedHeaders: ['*'],
          maxAge: 3600,
        },
      ],

      // Deletion protection
      removalPolicy: environmentName === 'prod'
        ? cdk.RemovalPolicy.RETAIN
        : cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: environmentName !== 'prod',
    });

    // Apply common tags
    const commonTags = ConfigHelper.getCommonTags(environmentName);
    Object.entries(commonTags).forEach(([key, value]) => {
      cdk.Tags.of(catalogBucket).add(key, value);
    });

    // Simplified catalog-specific tags
    cdk.Tags.of(catalogBucket).add('Purpose', 'RawParquetStorage');
    cdk.Tags.of(catalogBucket).add('Layer', 'DataLake');
    cdk.Tags.of(catalogBucket).add('DataFormat', 'Parquet');

    // Output catalog bucket information
    new cdk.CfnOutput(this, 'CatalogBucketArn', {
      value: catalogBucket.bucketArn,
      description: 'ARN of the catalog S3 bucket for raw parquet files',
      exportName: `${projectName}-CatalogBucketArn`,
    });

    new cdk.CfnOutput(this, 'CatalogBucketName', {
      value: this.catalogBucketName,
      description: 'S3 bucket name for raw parquet files',
      exportName: `${projectName}-CatalogBucketName`,
    });

    return catalogBucket;
  }

  /**
   * Creates a simplified Lambda function for creating raw parquet files
   */
  private createSimpleCatalogLambda(props: Omit<CatalogConstructProps, 'config'> & { config: EnvironmentConfig }): lambda.Function {
    const {
      environmentName,
      projectName,
      config,
      lambdaPrefix,
      account,
      region
    } = props;

    // ========================================
    // IAM Role for Simple Catalog Lambda
    // ========================================
    let catalogRole: iam.IRole;

    // For LocalStack (account 000000000000), create the role inline
    // For real AWS, use existing IAM role or create simplified one
    if (account === '000000000000') {
      console.log('🔧 Creating simplified Lambda catalog role for LocalStack');
      catalogRole = new iam.Role(this, 'SimpleCatalogRole', {
        assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
        managedPolicies: [
          iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
        ],
        inlinePolicies: {
          S3Access: new iam.PolicyDocument({
            statements: [
              new iam.PolicyStatement({
                effect: iam.Effect.ALLOW,
                actions: [
                  's3:GetObject',
                  's3:PutObject',
                  's3:DeleteObject',
                  's3:ListBucket'
                ],
                resources: [
                  `arn:aws:s3:::${this.catalogBucketName}`,
                  `arn:aws:s3:::${this.catalogBucketName}/*`
                ]
              })
            ]
          })
        }
      });
    } else {
      // Use existing IAM role for real AWS environments (without Glue permissions)
      catalogRole = iam.Role.fromRoleArn(
        this,
        'SimpleCatalogRole',
        `arn:aws:iam::${account}:role/catalunya-lambda-simple-catalog-role-${environmentName}`
      );
    }

    // ========================================
    // Simple Catalog Lambda
    // ========================================
    const catalogLambda = new lambda.Function(this, 'SimpleCatalogLambda', {
      functionName: `${lambdaPrefix}-simple-catalog`,
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: 'catalog_initializer.lambda_handler',
      code: lambda.Code.fromAsset('../lambda/catalog', {
        bundling: {
          image: lambda.Runtime.PYTHON_3_9.bundlingImage,
          command: [
            'bash', '-c', [
              // Install minimal dependencies for parquet creation
              'pip install pandas fastparquet -t /asset-output',
              'cp -au . /asset-output'
            ].join(' && ')
          ],
        },
      }),
      timeout: cdk.Duration.seconds(60), // Reduced timeout for simple operations
      memorySize: 256, // Reduced memory for simple parquet creation
      role: catalogRole,
      environment: {
        CATALOG_BUCKET_NAME: this.catalogBucketName,
        ENVIRONMENT: environmentName,
        REGION: region
      },
      description: `Simple Catalog Lambda for ${environmentName} environment - Creates raw parquet files`,
    });

    // ========================================
    // Tags and Outputs
    // ========================================
    const commonTags = ConfigHelper.getCommonTags(environmentName);
    Object.entries(commonTags).forEach(([key, value]) => {
      cdk.Tags.of(catalogLambda).add(key, value);
    });

    // Simplified tags
    cdk.Tags.of(catalogLambda).add('Purpose', 'ParquetGeneration');
    cdk.Tags.of(catalogLambda).add('Layer', 'DataProcessing');
    cdk.Tags.of(catalogLambda).add('Complexity', 'Simple');

    // Lambda outputs
    new cdk.CfnOutput(this, 'SimpleCatalogLambdaArn', {
      value: catalogLambda.functionArn,
      description: 'ARN of the Simple Catalog Lambda function',
      exportName: `${projectName}-SimpleCatalogLambdaArn`,
    });

    new cdk.CfnOutput(this, 'SimpleCatalogLambdaName', {
      value: catalogLambda.functionName,
      description: 'Name of the Simple Catalog Lambda function',
      exportName: `${projectName}-SimpleCatalogLambdaName`,
    });

    return catalogLambda;
  }
}