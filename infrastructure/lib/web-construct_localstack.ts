import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import {
  aws_s3 as s3,
  aws_iam as iam
} from 'aws-cdk-lib';
import { ConfigHelper } from './config';

export interface WebConstructLocalStackProps {
  projectName: string,
  environmentName: string;
  accountId: string;
  bucketName: string;
}

export class WebConstructLocalStack extends Construct {
  public readonly websiteBucket: s3.Bucket;

  constructor(scope: Construct, id: string, props: WebConstructLocalStackProps) {
    super(scope, id);

    const { projectName, environmentName, accountId, bucketName } = props;


    this.websiteBucket = new s3.Bucket(this, 'WebsiteBucket', {
      bucketName,
      versioned: false,
      publicReadAccess: false,
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

    cdk.Tags.of(this.websiteBucket).add('Purpose', 'StaticWebsite');
    cdk.Tags.of(this.websiteBucket).add('Layer', 'Presentation');
    cdk.Tags.of(this.websiteBucket).add('DataClassification', 'Public');

    new cdk.CfnOutput(this, 'BucketName', {
      value: this.websiteBucket.bucketName,
      description: 'Static website S3 bucket name',
      exportName: `${projectName}-WebsiteBucket-${environmentName}`,
    });

  }
}
