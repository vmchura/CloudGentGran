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
  public readonly serviceTypeCatalogLambda: lambda.Function;
  public readonly municipalsCatalogLambda: lambda.Function;

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
    this.serviceTypeCatalogLambda = this.createServiceTypeCatalogLambda({
          environmentName,
          projectName,
          config,
          dataBucketName: props.dataBucketName,
          athenaDatabaseName: props.athenaDatabaseName,
          lambdaPrefix,
          account,
          region
        });
    this.municipalsCatalogLambda = this.createMunicipalsCatalogLambda({
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
          enabled: true,
          transitions: [
            {
              storageClass: s3.StorageClass.INFREQUENT_ACCESS,
              transitionAfter: cdk.Duration.days(30),
            },
          ],
        }
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
  private createServiceTypeCatalogLambda(props: Omit<CatalogConstructProps, 'config'> & { config: EnvironmentConfig }): lambda.Function {
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
      catalogRole = new iam.Role(this, 'ServiceTypeCatalogRole', {
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
        'ServiceTypeCatalogRole',
        `arn:aws:iam::${account}:role/catalunya-lambda-simple-catalog-role-${environmentName}`
      );
    }

    // ========================================
    // Simple Catalog Lambda
    // ========================================
    const serviceTypeCatalogLambda = new lambda.Function(this, 'ServiceTypeCatalogLambda', {
      functionName: `${lambdaPrefix}-service-type-catalog`,
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: 'service_type_initializer.lambda_handler',
      code: lambda.Code.fromAsset('../lambda/catalog/service_type', {
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
      cdk.Tags.of(serviceTypeCatalogLambda).add(key, value);
    });

    // Simplified tags
    cdk.Tags.of(serviceTypeCatalogLambda).add('Purpose', 'ParquetGeneration');
    cdk.Tags.of(serviceTypeCatalogLambda).add('Layer', 'DataProcessing');
    cdk.Tags.of(serviceTypeCatalogLambda).add('Complexity', 'Simple');

    // Lambda outputs
    new cdk.CfnOutput(this, 'ServiceTypeCatalogLambdaArn', {
      value: serviceTypeCatalogLambda.functionArn,
      description: 'ARN of the ServiceType Catalog Lambda function',
      exportName: `${projectName}-ServiceTypeCatalogLambdaArn`,
    });

    new cdk.CfnOutput(this, 'ServiceTypeCatalogLambdaName', {
      value: serviceTypeCatalogLambda.functionName,
      description: 'Name of the ServiceType Catalog Lambda function',
      exportName: `${projectName}-ServiceTypeCatalogLambdaName`,
    });

    return serviceTypeCatalogLambda;
  }
private createMunicipalsCatalogLambda(props: Omit<CatalogConstructProps, 'config'> & { config: EnvironmentConfig }): lambda.Function {
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
      catalogRole = new iam.Role(this, 'MunicipalsCatalogRole', {
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
        'MunicipalsCatalogRole',
        `arn:aws:iam::${account}:role/catalunya-lambda-simple-catalog-role-${environmentName}`
      );
    }

    // ========================================
    // Simple Catalog Lambda
    // ========================================

    const municipalsCatalogLambda = new lambda.Function(this, 'MunicipalsCatalogLambda', {
          functionName: `${lambdaPrefix}-municipals-catalog`,
          runtime: lambda.Runtime.PYTHON_3_9,
          handler: 'municipals_initializer.lambda_handler',
          code: lambda.Code.fromAsset('../lambda/catalog/municipals', {
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
          memorySize: 512, // Reduced memory for simple parquet creation
          role: catalogRole,
          environment: {
            CATALOG_BUCKET_NAME: this.catalogBucketName,
            SEMANTIC_IDENTIFIER: 'municipals',
            DATASET_IDENTIFIER: '9aju-tpwc',
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
      cdk.Tags.of(municipalsCatalogLambda).add(key, value);
    });

    // Simplified tags
    cdk.Tags.of(municipalsCatalogLambda).add('Purpose', 'ParquetGeneration');
    cdk.Tags.of(municipalsCatalogLambda).add('Layer', 'DataProcessing');
    cdk.Tags.of(municipalsCatalogLambda).add('Complexity', 'Simple');

    // Lambda outputs
    new cdk.CfnOutput(this, 'MunicipalsCatalogLambdaArn', {
      value: municipalsCatalogLambda.functionArn,
      description: 'ARN of the Simple Catalog Lambda function',
      exportName: `${projectName}-MunicipalsCatalogLambdaArn`,
    });

    new cdk.CfnOutput(this, 'MunicipalsCatalogLambdaName', {
      value: municipalsCatalogLambda.functionName,
      description: 'Name of the Municipals Catalog Lambda function',
      exportName: `${projectName}-MunicipalsCatalogLambdaName`,
    });

    return municipalsCatalogLambda;
  }
}