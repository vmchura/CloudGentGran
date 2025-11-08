import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import {
  aws_s3 as s3,
  aws_cloudfront as cloudfront,
  aws_cloudfront_origins as origins,
  aws_route53 as route53,
  aws_route53_targets as targets,
  aws_certificatemanager as acm,
  aws_iam as iam
} from 'aws-cdk-lib';
import { ConfigHelper } from './config';

export interface WebConstructProps {
  environmentName: string;
  projectName: string;
  domainName: string;
  subdomain?: string;
  accountId: string;
  certificateId: string;
}

export class WebConstruct extends Construct {
  public readonly websiteBucket: s3.Bucket;
  public readonly distribution: cloudfront.Distribution;
  public readonly siteDomain: string;

  constructor(scope: Construct, id: string, props: WebConstructProps) {
    super(scope, id);

    const { environmentName, projectName, domainName, subdomain, accountId, certificateId, bucketName } = props;

    this.siteDomain = subdomain ? `${subdomain}.${domainName}` : domainName;
    const certificateArn = `arn:aws:acm:us-east-1:${accountId}:certificate/${certificateId}`;

    this.websiteBucket = new s3.Bucket(this, 'WebsiteBucket', {
      bucketName,
      versioned: false,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      publicReadAccess: false,
      removalPolicy: environmentName === 'prod'
        ? cdk.RemovalPolicy.RETAIN
        : cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: environmentName !== 'prod',
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      cors: [
        {
          allowedMethods: [s3.HttpMethods.GET, s3.HttpMethods.HEAD],
          allowedOrigins: ['*'],
          allowedHeaders: ['*'],
          maxAge: 3600,
        },
      ],
    });

    const originAccessIdentity = new cloudfront.OriginAccessIdentity(this, 'OAI', {
      comment: `OAI for ${this.siteDomain}`,
    });

    this.websiteBucket.addToResourcePolicy(
      new iam.PolicyStatement({
        actions: ['s3:GetObject'],
        resources: [`${this.websiteBucket.bucketArn}/*`],
        principals: [new iam.CanonicalUserPrincipal(originAccessIdentity.cloudFrontOriginAccessIdentityS3CanonicalUserId)],
      })
    );

    const certificate = acm.Certificate.fromCertificateArn(this, 'Certificate', certificateArn);

    this.distribution = new cloudfront.Distribution(this, 'WebsiteDistribution', {
      defaultBehavior: {
        origin: new origins.S3Origin(this.websiteBucket, {
          originAccessIdentity,
        }),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
        cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
        compress: true,
      },
      defaultRootObject: 'index.html',
      errorResponses: [
        {
          httpStatus: 403,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
          ttl: cdk.Duration.minutes(5),
        },
        {
          httpStatus: 404,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
          ttl: cdk.Duration.minutes(5),
        },
      ],
      domainNames: [this.siteDomain],
      certificate,
      minimumProtocolVersion: cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
      httpVersion: cloudfront.HttpVersion.HTTP2_AND_3,
      priceClass: cloudfront.PriceClass.PRICE_CLASS_100,
      enableLogging: false,
    });

    const zone = route53.HostedZone.fromLookup(this, 'Zone', { domainName });

    new route53.ARecord(this, 'AliasRecord', {
      recordName: this.siteDomain,
      target: route53.RecordTarget.fromAlias(new targets.CloudFrontTarget(this.distribution)),
      zone,
    });

    const commonTags = ConfigHelper.getCommonTags(environmentName);
    Object.entries(commonTags).forEach(([key, value]) => {
      cdk.Tags.of(this.websiteBucket).add(key, value);
      cdk.Tags.of(this.distribution).add(key, value);
    });

    cdk.Tags.of(this.websiteBucket).add('Purpose', 'StaticWebsite');
    cdk.Tags.of(this.websiteBucket).add('Layer', 'Presentation');
    cdk.Tags.of(this.websiteBucket).add('DataClassification', 'Public');

    new cdk.CfnOutput(this, 'BucketName', {
      value: this.websiteBucket.bucketName,
      description: 'Static website S3 bucket name',
      exportName: `${projectName}-WebsiteBucket-${environmentName}`,
    });

    new cdk.CfnOutput(this, 'DistributionId', {
      value: this.distribution.distributionId,
      description: 'CloudFront distribution ID',
      exportName: `${projectName}-DistributionId-${environmentName}`,
    });

    new cdk.CfnOutput(this, 'DistributionDomain', {
      value: this.distribution.domainName,
      description: 'CloudFront distribution domain',
      exportName: `${projectName}-DistributionDomain-${environmentName}`,
    });

    new cdk.CfnOutput(this, 'WebsiteURL', {
      value: `https://${this.siteDomain}`,
      description: 'Website URL',
      exportName: `${projectName}-WebsiteURL-${environmentName}`,
    });
  }
}
