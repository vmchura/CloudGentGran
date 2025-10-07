import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';
import { EnvironmentConfig, ConfigHelper } from './config';

export interface S3ConstructProps {
  environmentName: string;
  projectName: string;
  config: EnvironmentConfig;
  bucketName: string;
  athenaResultsBucketName: string;
}

export class S3Construct extends Construct {
  public readonly dataBucket: s3.Bucket;
  public readonly athenaResultsBucket: s3.Bucket;

  constructor(scope: Construct, id: string, props: S3ConstructProps) {
    super(scope, id);

    const { environmentName, projectName, config, bucketName, athenaResultsBucketName } = props;

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
        expiration: cdk.Duration.days(config.retentionPeriod),
      },
    ];

    // Create the main data bucket
    this.dataBucket = new s3.Bucket(this, 'DataBucket', {
      bucketName: bucketName,

      publicReadAccess: false,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,

      // Versioning for data protection
      versioned: environmentName === 'prod',

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
      removalPolicy: environmentName === 'prod'
        ? cdk.RemovalPolicy.RETAIN
        : cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: environmentName !== 'prod',
    });

    // Create dedicated Athena results bucket
    this.athenaResultsBucket = new s3.Bucket(this, 'AthenaResultsBucket', {
      bucketName: athenaResultsBucketName,

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
      removalPolicy: environmentName === 'prod'
        ? cdk.RemovalPolicy.RETAIN
        : cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: environmentName !== 'prod',
    });

    // Apply common tags
    const commonTags = ConfigHelper.getCommonTags(environmentName);

    [this.dataBucket, this.athenaResultsBucket].forEach(bucket => {
      Object.entries(commonTags).forEach(([key, value]) => {
        cdk.Tags.of(bucket).add(key, value);
      });
    });

    // Additional S3 bucket tags
    cdk.Tags.of(this.dataBucket).add('Purpose', 'DataLake');
    cdk.Tags.of(this.dataBucket).add('Layer', 'Storage');
    cdk.Tags.of(this.dataBucket).add('DataClassification', 'OpenData');

    cdk.Tags.of(this.athenaResultsBucket).add('Purpose', 'QueryResults');
    cdk.Tags.of(this.athenaResultsBucket).add('Layer', 'Analytics');
    cdk.Tags.of(this.athenaResultsBucket).add('DataClassification', 'Processed');

    // Output bucket information
    new cdk.CfnOutput(this, 'S3BucketArn', {
      value: this.dataBucket.bucketArn,
      description: 'ARN of the main data S3 bucket',
      exportName: `${projectName}-S3BucketArn`,
    });

    new cdk.CfnOutput(this, 'S3BucketDomainName', {
      value: this.dataBucket.bucketDomainName,
      description: 'Domain name of the main data S3 bucket',
      exportName: `${projectName}-S3BucketDomainName`,
    });

    new cdk.CfnOutput(this, 'AthenaResultsBucketArn', {
      value: this.athenaResultsBucket.bucketArn,
      description: 'ARN of the Athena results S3 bucket',
      exportName: `${projectName}-AthenaResultsBucketArn`,
    });
  }
}