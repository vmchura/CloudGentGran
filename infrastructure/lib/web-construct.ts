import * as cdk from 'aws-cdk-lib';
import { aws_s3 as s3, aws_cloudfront as cloudfront, aws_cloudfront_origins as origins, aws_route53 as route53, aws_route53_targets as targets } from 'aws-cdk-lib';
import { EnvironmentConfig, ConfigHelper } from './config';

export class StaticWebsiteStack extends cdk.Stack {
  constructor(scope: cdk.App, id: string, props: {
    environmentName: string,
    domainName: string,
    subdomain: string,
  }) {
    super(scope, id, props);

    const { environmentName, domainName, subdomain } = props;

    const siteDomain = `${subdomain}.${domainName}`;
    const bucketName = `${siteDomain.replace(/\./g, '-')}-${environmentName}`;

    // --- 1️⃣ S3 Bucket ---
    const websiteBucket = new s3.Bucket(this, 'WebsiteBucket', {
      bucketName,
      versioned: environmentName === 'prod',
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      publicReadAccess: false,
      removalPolicy: environmentName === 'prod'
        ? cdk.RemovalPolicy.RETAIN
        : cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: environmentName !== 'prod',

      // Optional: lifecycle for assets
      lifecycleRules: [
        {
          id: 'ExpireOldAssets',
          prefix: 'assets/',
          enabled: true,
          expiration: cdk.Duration.days(90),
        },
      ],

      cors: [
        {
          allowedMethods: [s3.HttpMethods.GET, s3.HttpMethods.HEAD],
          allowedOrigins: ['*'],
          allowedHeaders: ['*'],
          maxAge: 3600,
        },
      ],
    });

    const commonTags = ConfigHelper.getCommonTags(environmentName);

      Object.entries(commonTags).forEach(([key, value]) => {
        cdk.Tags.of(this.websiteBucket).add(key, value);
      });
  // Additional S3 bucket tags
      cdk.Tags.of(this.websiteBucket).add('Purpose', 'DataService');
      cdk.Tags.of(this.websiteBucket).add('Layer', 'Service');
      cdk.Tags.of(this.websiteBucket).add('DataClassification', 'Processed');

    // --- 2️⃣ CloudFront distribution ---
    const distribution = new cloudfront.Distribution(this, 'WebsiteDistribution', {
      defaultBehavior: {
        origin: new origins.S3Origin(websiteBucket),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
      },
      defaultRootObject: 'index.html',
      errorResponses: [
        {
          httpStatus: 404,
          responseHttpStatus: 404,
          responsePagePath: '/404.html',
          ttl: cdk.Duration.minutes(30),
        },
      ],
      domainNames: [siteDomain],
      certificate: cloudfront.ViewerCertificate.fromAcmCertificate({
        certificateArn: `arn:aws:acm:REGION:ACCOUNT_ID:certificate/CERT_ID`, // <-- Replace with your cert
        env: { region: 'us-east-1' }, // ACM cert for CloudFront must be in us-east-1
      }),
    });

    // --- 3️⃣ Route 53 DNS record ---
    const zone = route53.HostedZone.fromLookup(this, 'Zone', { domainName });
    new route53.ARecord(this, 'AliasRecord', {
      recordName: siteDomain,
      target: route53.RecordTarget.fromAlias(new targets.CloudFrontTarget(distribution)),
      zone,
    });

    // --- 4️⃣ Output the URLs ---
    new cdk.CfnOutput(this, 'BucketName', { value: websiteBucket.bucketName });
    new cdk.CfnOutput(this, 'DistributionDomain', { value: distribution.domainName });
    new cdk.CfnOutput(this, 'WebsiteURL', { value: `https://${siteDomain}` });
  }
}
