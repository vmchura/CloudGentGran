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
  catalogBucketName: string;
  athenaDatabaseName: string;
  glueExecutorRole: iam.Role;
}

export class GlueConstruct extends Construct {
  public readonly socialServicesTable: glue.CfnTable;
  public readonly municipalsTable: glue.CfnTable;
  public readonly serviceTypeTable: glue.CfnTable;
  public readonly serviceQualificationTable: glue.CfnTable;

  constructor(scope: Construct, id: string, props: GlueConstructProps) {
    super(scope, id);

    const {
      environmentName,
      projectName,
      athenaDatabaseName,
      dataBucketName,
      catalogBucketName,
      glueExecutorRole
    } = props;

    this.socialServicesTable = this.createSocialServicesTable(
      athenaDatabaseName,
      dataBucketName,
      environmentName
    );

    this.municipalsTable = this.createMunicipalsTable(
      athenaDatabaseName,
      catalogBucketName
    );

    this.serviceTypeTable = this.createServiceTypeTable(
	athenaDatabaseName,
	catalogBucketName
    );
    this.serviceQualificationTable = this.createServiceQualificationTable(
	athenaDatabaseName,
	catalogBucketName
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

  private createMunicipalsTable(
    databaseName: string,
    catalogBucketName: string
  ): glue.CfnTable {
    return new glue.CfnTable(this, 'MunicipalsTable', {
      catalogId: cdk.Aws.ACCOUNT_ID,
      databaseName: databaseName,
      tableInput: {
        name: 'municipals',
        tableType: 'EXTERNAL_TABLE',
        storageDescriptor: {
          columns: [
            { name: 'municipal_id', type: 'string' },
            { name: 'municipal_name', type: 'string' },
            { name: 'comarca_id', type: 'string' },
            { name: 'comarca_name', type: 'string' }
          ],
          location: `s3://${catalogBucketName}/municipals/`,
          inputFormat: 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat',
          outputFormat: 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat',
          serdeInfo: {
            serializationLibrary: 'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe'
          }
        }
      }
    });
  }

  private createServiceTypeTable(
    databaseName: string,
    catalogBucketName: string
  ): glue.CfnTable {
    return new glue.CfnTable(this, 'ServiceTypeTable', {
      catalogId: cdk.Aws.ACCOUNT_ID,
      databaseName: databaseName,
      tableInput: {
        name: 'service_type',
        tableType: 'EXTERNAL_TABLE',
        storageDescriptor: {
          columns: [
            { name: 'service_type_id', type: 'string' },
            { name: 'service_type_description', type: 'string' },
            { name: 'created_at', type: 'string' }
          ],
          location: `s3://${catalogBucketName}/service_type/`,
          inputFormat: 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat',
          outputFormat: 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat',
          serdeInfo: {
            serializationLibrary: 'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe'
          }
        }
      }
    });
  }

  private createServiceQualificationTable(
    databaseName: string,
    catalogBucketName: string
  ): glue.CfnTable {
    return new glue.CfnTable(this, 'ServiceQualificationTable', {
      catalogId: cdk.Aws.ACCOUNT_ID,
      databaseName: databaseName,
      tableInput: {
        name: 'service_qualification',
        tableType: 'EXTERNAL_TABLE',
        storageDescriptor: {
          columns: [
            { name: 'service_qualification_id', type: 'string' },
            { name: 'service_qualification_description', type: 'string' },
            { name: 'created_at', type: 'string' }
          ],
          location: `s3://${catalogBucketName}/service_qualification/`,
          inputFormat: 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat',
          outputFormat: 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat',
          serdeInfo: {
            serializationLibrary: 'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe'
          }
        }
      }
    });
  }
}
