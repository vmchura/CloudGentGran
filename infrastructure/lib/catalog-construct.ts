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
      dataBucketName,
      athenaDatabaseName,
      lambdaPrefix,
      account,
      region
    } = props;

    // Generate catalog bucket name
    this.catalogBucketName = ConfigHelper.getResourceName('catalunya-catalog', environmentName);

    // Create catalog infrastructure
    this.catalogBucket = this.createCatalogBucket(environmentName, projectName);
    this.catalogInitializerLambda = this.createCatalogInitializerLambda({
      environmentName,
      projectName,
      config,
      dataBucketName,
      athenaDatabaseName,
      lambdaPrefix,
      account,
      region
    });
  }

  /**
   * Creates the S3 bucket for storing dimension tables and catalog metadata
   */
  private createCatalogBucket(environmentName: string, projectName: string): s3.Bucket {
    const catalogBucket = new s3.Bucket(this, 'CatalogBucket', {
      bucketName: this.catalogBucketName,

      publicReadAccess: false,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,

      // Versioning for dimension table protection
      versioned: environmentName === 'prod',

      // Lifecycle rules for catalog data management
      lifecycleRules: [
        {
          id: 'DimensionTablesRetention',
          prefix: 'dimensions/',
          enabled: true,
          transitions: [
            {
              storageClass: s3.StorageClass.INFREQUENT_ACCESS,
              transitionAfter: cdk.Duration.days(90), // Dimension tables accessed less frequently
            },
          ],
        },
        {
          id: 'TemporaryFilesCleanup',
          prefix: 'temp/',
          enabled: true,
          expiration: cdk.Duration.days(7), // Clean up temporary processing files
        },
      ],

      // CORS configuration for potential catalog web access
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

    // Catalog-specific tags
    cdk.Tags.of(catalogBucket).add('Purpose', 'CatalogStorage');
    cdk.Tags.of(catalogBucket).add('Layer', 'Catalog');
    cdk.Tags.of(catalogBucket).add('DataClassification', 'DimensionTables');

    // Output catalog bucket information
    new cdk.CfnOutput(this, 'CatalogBucketArn', {
      value: catalogBucket.bucketArn,
      description: 'ARN of the catalog S3 bucket for dimension tables',
      exportName: `${projectName}-CatalogBucketArn`,
    });

    new cdk.CfnOutput(this, 'CatalogBucketName', {
      value: this.catalogBucketName,
      description: 'S3 bucket name for dimension tables and catalog data',
      exportName: `${projectName}-CatalogBucketName`,
    });

    return catalogBucket;
  }

  /**
   * Creates the catalog initializer Lambda function for managing dimension tables
   */
  private createCatalogInitializerLambda(props: Omit<CatalogConstructProps, 'config'> & { config: EnvironmentConfig }): lambda.Function {
    const {
      environmentName,
      projectName,
      config,
      dataBucketName,
      athenaDatabaseName,
      lambdaPrefix,
      account,
      region
    } = props;

    // ========================================
    // IAM Role for Catalog Initializer Lambda
    // ========================================
    let catalogRole: iam.IRole;

    // For LocalStack (account 000000000000), create the role inline
    // For real AWS, use existing IAM role
    if (account === '000000000000') {
      console.log('🔧 Creating Lambda catalog role inline for LocalStack');
      catalogRole = new iam.Role(this, 'CatalogInitializerRole', {
        assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
        managedPolicies: [
          iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
        ],
        inlinePolicies: {
          CatalogAccess: new iam.PolicyDocument({
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
                  `arn:aws:s3:::${this.catalogBucketName}/*`,
                  `arn:aws:s3:::${dataBucketName}`,
                  `arn:aws:s3:::${dataBucketName}/*`
                ]
              }),
              new iam.PolicyStatement({
                effect: iam.Effect.ALLOW,
                actions: [
                  'glue:GetDatabase',
                  'glue:GetTable',
                  'glue:CreateTable',
                  'glue:UpdateTable',
                  'glue:DeleteTable',
                  'glue:GetPartitions'
                ],
                resources: [
                  `arn:aws:glue:${region}:${account}:catalog`,
                  `arn:aws:glue:${region}:${account}:database/${athenaDatabaseName}`,
                  `arn:aws:glue:${region}:${account}:table/${athenaDatabaseName}/*`
                ]
              })
            ]
          })
        }
      });
    } else {
      // Use existing IAM role for real AWS environments
      catalogRole = iam.Role.fromRoleArn(
        this,
        'CatalogInitializerRole',
        `arn:aws:iam::${account}:role/catalunya-lambda-catalog-role-${environmentName}`
      );
    }

    // ========================================
    // Catalog Initializer Lambda
    // ========================================
    const catalogInitializerLambda = new lambda.Function(this, 'CatalogInitializerLambda', {
      functionName: `${lambdaPrefix}-catalog-initializer`,
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: 'catalog_initializer.lambda_handler',
      code: lambda.Code.fromAsset('../lambda/catalog', {
        bundling: {
          image: lambda.Runtime.PYTHON_3_9.bundlingImage,
          command: [
            'bash', '-c', [
              // Install only what’s needed
              'pip install pandas fastparquet -t /asset-output',
              'cp -au . /asset-output'
            ].join(' && ')
          ],
        },
      }),
      timeout: cdk.Duration.seconds(300),
      memorySize: 512,
      role: catalogRole,
      environment: {
        CATALOG_BUCKET_NAME: this.catalogBucketName,
        DATA_BUCKET_NAME: dataBucketName,
        GLUE_DATABASE_NAME: athenaDatabaseName,
        ENVIRONMENT: environmentName,
        REGION: region
      },
      description: `Catalog Initializer Lambda for ${environmentName} environment - Manages dimension tables`,
    });


    // ========================================
    // Tags and Outputs
    // ========================================
    const commonTags = ConfigHelper.getCommonTags(environmentName);
    Object.entries(commonTags).forEach(([key, value]) => {
      cdk.Tags.of(catalogInitializerLambda).add(key, value);
    });

    // Catalog-specific tags
    cdk.Tags.of(catalogInitializerLambda).add('Purpose', 'CatalogManagement');
    cdk.Tags.of(catalogInitializerLambda).add('Layer', 'Catalog');
    cdk.Tags.of(catalogInitializerLambda).add('DataFlow', 'DimensionTables');

    // Lambda outputs
    new cdk.CfnOutput(this, 'CatalogInitializerLambdaArn', {
      value: catalogInitializerLambda.functionArn,
      description: 'ARN of the Catalog Initializer Lambda function',
      exportName: `${projectName}-CatalogInitializerLambdaArn`,
    });

    new cdk.CfnOutput(this, 'CatalogInitializerLambdaName', {
      value: catalogInitializerLambda.functionName,
      description: 'Name of the Catalog Initializer Lambda function',
      exportName: `${projectName}-CatalogInitializerLambdaName`,
    });

    return catalogInitializerLambda;
  }
}