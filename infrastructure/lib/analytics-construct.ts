import * as cdk from 'aws-cdk-lib';
import * as glue from 'aws-cdk-lib/aws-glue';
import * as athena from 'aws-cdk-lib/aws-athena';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';
import { EnvironmentConfig, ConfigHelper } from './config';

export interface AnalyticsConstructProps {
  environmentName: string;
  projectName: string;
  config: EnvironmentConfig;
  account: string;
  athenaDatabaseName: string;
  athenaWorkgroupName: string;
  athenaResultsBucketName: string;
  athenaResultsBucket: s3.Bucket;
}

export class AnalyticsConstruct extends Construct {
  public readonly glueDatabase: glue.CfnDatabase;
  public readonly athenaWorkgroup: athena.CfnWorkGroup;

  constructor(scope: Construct, id: string, props: AnalyticsConstructProps) {
    super(scope, id);

    const {
      environmentName,
      projectName,
      config,
      account,
      athenaDatabaseName,
      athenaWorkgroupName,
      athenaResultsBucketName,
      athenaResultsBucket
    } = props;

    // Create Glue Data Catalog
    this.glueDatabase = this.createGlueDataCatalog({
      environmentName,
      projectName,
      account,
      athenaDatabaseName
    });

    // Create Athena Infrastructure
    this.athenaWorkgroup = this.createAthenaInfrastructure({
      environmentName,
      projectName,
      athenaWorkgroupName,
      athenaResultsBucketName,
      athenaResultsBucket
    });
  }

  /**
   * Creates AWS Glue Data Catalog database for storing table metadata
   */
  private createGlueDataCatalog(props: {
    environmentName: string;
    projectName: string;
    account: string;
    athenaDatabaseName: string;
  }): glue.CfnDatabase {
    const { environmentName, projectName, account, athenaDatabaseName } = props;

    // ========================================
    // Glue Database
    // ========================================

    const glueDatabase = new glue.CfnDatabase(this, 'GlueDatabase', {
      catalogId: account,
      databaseInput: {
        name: athenaDatabaseName,
        description: `Catalunya data catalog for ${environmentName} environment`,
        parameters: {
          'classification': 'parquet',
          'typeOfData': 'file',
          'creator': 'Catalunya Data Pipeline',
          'environment': environmentName,
        },
      },
    });

    // Tag the database
    const commonTags = ConfigHelper.getCommonTags(environmentName);
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
      exportName: `${projectName}-GlueDatabaseName`,
    });

    return glueDatabase;
  }

  /**
   * Creates Athena workgroup with query result location and cost controls
   */
  private createAthenaInfrastructure(props: {
    environmentName: string;
    projectName: string;
    athenaWorkgroupName: string;
    athenaResultsBucketName: string;
    athenaResultsBucket: s3.Bucket;
  }): athena.CfnWorkGroup {
    const {
      environmentName,
      projectName,
      athenaWorkgroupName,
      athenaResultsBucketName,
      athenaResultsBucket
    } = props;

    // ========================================
    // Athena Workgroup
    // ========================================

    const workgroupConfiguration: athena.CfnWorkGroup.WorkGroupConfigurationProperty = {
      resultConfiguration: {
        outputLocation: `s3://${athenaResultsBucketName}/query-results/`,
        encryptionConfiguration: {
          encryptionOption: 'SSE_S3',
        },
      },
      enforceWorkGroupConfiguration: true,
      publishCloudWatchMetricsEnabled: true,
      bytesScannedCutoffPerQuery: environmentName === 'prod'
        ? 10 * 1024 * 1024 * 1024 // 10GB limit for prod
        : 1 * 1024 * 1024 * 1024,  // 1GB limit for dev
      requesterPaysEnabled: false,
    };

    const athenaWorkgroup = new athena.CfnWorkGroup(this, 'AthenaWorkgroupResource', {
      name: athenaWorkgroupName,
      description: `Athena workgroup for Catalunya data pipeline - ${environmentName} environment`,
      state: 'ENABLED',
      workGroupConfiguration: workgroupConfiguration,
      tags: [
        {
          key: 'Environment',
          value: environmentName,
        },
        {
          key: 'Project',
          value: projectName,
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
    athenaWorkgroup.addDependency(athenaResultsBucket.node.defaultChild as cdk.CfnResource);

    return athenaWorkgroup;
  }
}