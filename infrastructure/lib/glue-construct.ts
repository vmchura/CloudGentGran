import * as cdk from 'aws-cdk-lib';
import * as glue from 'aws-cdk-lib/aws-glue';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import { EnvironmentConfig, ConfigHelper } from './config';

export interface GlueConstructProps {
  environmentName: string;
  projectName: string;
  config: EnvironmentConfig;
  dataBucketName: string;
  athenaDatabaseName: string;
  glueExecutorRole: iam.Role;
}

export class GlueConstruct extends Construct {
  public readonly socialServicesTable: glue.CfnTable;

  constructor(scope: Construct, id: string, props: GlueConstructProps) {
    super(scope, id);

    const {
      environmentName,
      projectName,
      athenaDatabaseName,
      dataBucketName,
      glueExecutorRole
    } = props;

    this.socialServicesTable = this.createSocialServicesTable(
      athenaDatabaseName,
      dataBucketName,
      environmentName
    );
  }

  private createSocialServicesTable(
    databaseName: string,
    bucketName: string,
    environmentName: string
  ): glue.CfnTable {
    return new glue.CfnTable(this, 'SocialServicesTable', {
      catalogId: cdk.Aws.ACCOUNT_ID,
      databaseName: databaseName,
      tableInput: {
        name: 'social_services',
        tableType: 'EXTERNAL_TABLE',
        storageDescriptor: {
          columns: [
            { name: 'social_service_register_id', type: 'string' },
            { name: 'inscription_date', type: 'date' },
            { name: 'capacity', type: 'int' },
            { name: 'service_type_id', type: 'string' },
            { name: 'service_qualification_id', type: 'string' },
            { name: 'municipal_id', type: 'string' },
            { name: 'comarca_id', type: 'string' }
          ],
          location: `s3://${bucketName}/staging/social_services/`,
          inputFormat: 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat',
          outputFormat: 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat',
          serdeInfo: {
            serializationLibrary: 'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe'
          }
        },
        partitionKeys: [
          { name: 'downloaded_date', type: 'string' }
        ]
      }
    });
  }
}