import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import { ConfigHelper, EnvironmentConfig } from './config';

export interface IamConstructProps {
  environmentName: string;
  projectName: string;
  config: EnvironmentConfig;
  account: string;
  region: string;
  bucketName: string;
  athenaResultsBucketName: string;
  athenaDatabaseName: string;
  athenaWorkgroupName: string;
  catalogBucketName: string;
}

export class IamConstruct extends Construct {
  // Lambda execution roles
  public readonly extractorExecutionRole: iam.Role;
  public readonly transformerExecutionRole: iam.Role;
  public readonly martExecutionRole: iam.Role;
  public readonly monitoringExecutionRole: iam.Role;
  public readonly catalogExecutorRole: iam.Role;
  public readonly airflowCrossAccountRole: iam.Role;

  // Orchestration roles
  public readonly airflowUser: iam.User;
  public readonly airflowAccessKey: iam.AccessKey;

  // Human roles
  public readonly dataEngineerRole: iam.Role;

  // IAM policies
  public readonly extractorPolicy: iam.ManagedPolicy;
  public readonly transformerPolicy: iam.ManagedPolicy;
  public readonly martExecutorPolicy: iam.ManagedPolicy;
  public readonly catalogExecutorPolicy: iam.ManagedPolicy;
  public readonly airflowCrossAccountPolicy: iam.ManagedPolicy;

  constructor(scope: Construct, id: string, props: IamConstructProps) {
    super(scope, id);

    const { environmentName, projectName, config, account, region, bucketName,
            athenaResultsBucketName, athenaDatabaseName, athenaWorkgroupName,
            catalogBucketName } = props;

    // Common tags for all IAM resources
    const commonTags = ConfigHelper.getCommonTags(environmentName);

    // ========================================
    // IAM Policies
    // ========================================

    // Lambda Extractor Policy
    this.extractorPolicy = new iam.ManagedPolicy(this, 'ExtractorPolicy', {
      managedPolicyName: `CatalunyaLambdaExtractorPolicy${environmentName.charAt(0).toUpperCase() + environmentName.slice(1)}`,
      description: `Lambda extractor permissions for Catalunya Data Pipeline (${environmentName})`,
      statements: [
        // CloudWatch Logs
        new iam.PolicyStatement({
          sid: 'CloudWatchLogGroups',
          effect: iam.Effect.ALLOW,
          actions: [
            'logs:CreateLogGroup',
            'logs:CreateLogStream',
            'logs:PutLogEvents',
            'logs:DescribeLogGroups',
            'logs:DescribeLogStreams',
          ],
          resources: [
            `arn:aws:logs:${region}:${account}:log-group:/aws/lambda/catalunya-${environmentName}-*`,
            `arn:aws:logs:${region}:${account}:log-group:/aws/lambda/catalunya-${environmentName}-*:*`,
          ],
        }),
        // S3 Data Bucket Read
        new iam.PolicyStatement({
          sid: 'S3DataBucketRead',
          effect: iam.Effect.ALLOW,
          actions: [
            's3:GetBucketLocation',
            's3:ListBucket',
          ],
          resources: [`arn:aws:s3:::${bucketName}`],
        }),
        // S3 Data Bucket Write (landing prefix)
        new iam.PolicyStatement({
          sid: 'S3DataBucketWrite',
          effect: iam.Effect.ALLOW,
          actions: [
            's3:PutObject',
            's3:PutObjectAcl',
            's3:GetObject',
            's3:GetObjectVersion',
          ],
          resources: [`arn:aws:s3:::${bucketName}/landing/*`],
        }),
        // X-Ray Permissions
        new iam.PolicyStatement({
          sid: 'XRayPermissions',
          effect: iam.Effect.ALLOW,
          actions: [
            'xray:PutTraceSegments',
            'xray:PutTelemetryRecords',
          ],
          resources: ['*'],
          conditions: {
            StringEquals: {
              'aws:RequestedRegion': region,
            },
          },
        }),
      ],
    });

    // Lambda Transformer Policy
    this.transformerPolicy = new iam.ManagedPolicy(this, 'TransformerPolicy', {
      managedPolicyName: `CatalunyaLambdaTransformerPolicy${environmentName.charAt(0).toUpperCase() + environmentName.slice(1)}`,
      description: `Lambda transformer permissions for Catalunya Data Pipeline (${environmentName})`,
      statements: [
        // CloudWatch Logs
        new iam.PolicyStatement({
          sid: 'CloudWatchLogGroups',
          effect: iam.Effect.ALLOW,
          actions: [
            'logs:CreateLogGroup',
            'logs:CreateLogStream',
            'logs:PutLogEvents',
            'logs:DescribeLogGroups',
            'logs:DescribeLogStreams',
          ],
          resources: [
            `arn:aws:logs:${region}:${account}:log-group:/aws/lambda/catalunya-${environmentName}-*`,
            `arn:aws:logs:${region}:${account}:log-group:/aws/lambda/catalunya-${environmentName}-*:*`,
          ],
        }),
        // S3 Data Bucket Read (landing prefix)
        new iam.PolicyStatement({
          sid: 'S3DataBucketRead',
          effect: iam.Effect.ALLOW,
          actions: [
            's3:GetBucketLocation',
            's3:ListBucket',
            's3:GetObject',
            's3:GetObjectVersion',
          ],
          resources: [
            `arn:aws:s3:::${bucketName}`,
            `arn:aws:s3:::${bucketName}/landing/*`,
          ],
        }),
        new iam.PolicyStatement({
          sid: 'S3CatalogBucketRead',
          effect: iam.Effect.ALLOW,
          actions: [
            's3:GetBucketLocation',
            's3:ListBucket',
            's3:GetObject',
            's3:GetObjectVersion',
          ],
          resources: [
            `arn:aws:s3:::${catalogBucketName}`,
            `arn:aws:s3:::${catalogBucketName}/*`,
          ],
        }),
        // S3 Data Bucket Write (staging prefix)
        new iam.PolicyStatement({
          sid: 'S3DataBucketWrite',
          effect: iam.Effect.ALLOW,
          actions: [
            's3:PutObject',
            's3:PutObjectAcl',
          ],
          resources: [`arn:aws:s3:::${bucketName}/staging/*`],
        }),
        // X-Ray Permissions
        new iam.PolicyStatement({
          sid: 'XRayPermissions',
          effect: iam.Effect.ALLOW,
          actions: [
            'xray:PutTraceSegments',
            'xray:PutTelemetryRecords',
          ],
          resources: ['*'],
          conditions: {
            StringEquals: {
              'aws:RequestedRegion': region,
            },
          },
        }),
      ],
    });

    // Mart Executor Policy (DBT/Athena)
    this.martExecutorPolicy = new iam.ManagedPolicy(this, 'MartExecutorPolicy', {
      managedPolicyName: `CatalunyaMartExecutorPolicy${environmentName.charAt(0).toUpperCase() + environmentName.slice(1)}`,
      description: `Mart/DBT executor permissions for Catalunya Data Pipeline (${environmentName})`,
      statements: [
        // CloudWatch Logs
        new iam.PolicyStatement({
          sid: 'CloudWatchLogGroups',
          effect: iam.Effect.ALLOW,
          actions: [
            'logs:CreateLogGroup',
            'logs:CreateLogStream',
            'logs:PutLogEvents',
            'logs:DescribeLogGroups',
            'logs:DescribeLogStreams',
          ],
          resources: [
            `arn:aws:logs:${region}:${account}:log-group:/aws/lambda/catalunya-${environmentName}-*`,
            `arn:aws:logs:${region}:${account}:log-group:/aws/lambda/catalunya-${environmentName}-*:*`,
          ],
        }),
        // S3 Staging Layer Read
        new iam.PolicyStatement({
          sid: 'S3StagingLayerRead',
          effect: iam.Effect.ALLOW,
          actions: [
            's3:GetBucketLocation',
            's3:ListBucket',
            's3:GetObject',
            's3:GetObjectVersion',
          ],
          resources: [
            `arn:aws:s3:::${bucketName}`,
            `arn:aws:s3:::${bucketName}/staging/*`,
          ],
        }),
        // S3 Marts Layer Write
        new iam.PolicyStatement({
          sid: 'S3MartsLayerWrite',
          effect: iam.Effect.ALLOW,
          actions: [
            's3:PutObject',
            's3:PutObjectAcl',
            's3:DeleteObject',
            's3:GetObject',
            's3:GetObjectVersion',
          ],
          resources: [`arn:aws:s3:::${bucketName}/marts/*`],
        }),
        // S3 Athena Results Access
        new iam.PolicyStatement({
          sid: 'S3AthenaResultsAccess',
          effect: iam.Effect.ALLOW,
          actions: [
            's3:GetBucketLocation',
            's3:ListBucket',
            's3:PutObject',
            's3:GetObject',
            's3:DeleteObject',
          ],
          resources: [
            `arn:aws:s3:::${athenaResultsBucketName}`,
            `arn:aws:s3:::${athenaResultsBucketName}/*`,
          ],
        }),
        // Glue Data Catalog Read
        new iam.PolicyStatement({
          sid: 'GlueDataCatalogRead',
          effect: iam.Effect.ALLOW,
          actions: [
            'glue:GetDatabase',
            'glue:GetTable',
            'glue:GetTables',
            'glue:GetPartition',
            'glue:GetPartitions',
            'glue:BatchGetPartition',
          ],
          resources: [
            `arn:aws:glue:${region}:${account}:catalog`,
            `arn:aws:glue:${region}:${account}:database/${athenaDatabaseName}`,
            `arn:aws:glue:${region}:${account}:table/${athenaDatabaseName}/*`,
          ],
        }),
        // Glue Data Catalog Write
        new iam.PolicyStatement({
          sid: 'GlueDataCatalogWrite',
          effect: iam.Effect.ALLOW,
          actions: [
            'glue:CreateTable',
            'glue:UpdateTable',
            'glue:DeleteTable',
            'glue:CreatePartition',
            'glue:UpdatePartition',
            'glue:DeletePartition',
            'glue:BatchCreatePartition',
            'glue:BatchUpdatePartition',
            'glue:BatchDeletePartition',
          ],
          resources: [
            `arn:aws:glue:${region}:${account}:catalog`,
            `arn:aws:glue:${region}:${account}:database/${athenaDatabaseName}`,
            `arn:aws:glue:${region}:${account}:table/${athenaDatabaseName}/*`,
          ],
        }),
        // Athena Query Execution
        new iam.PolicyStatement({
          sid: 'AthenaQueryExecution',
          effect: iam.Effect.ALLOW,
          actions: [
            'athena:StartQueryExecution',
            'athena:StopQueryExecution',
            'athena:GetQueryExecution',
            'athena:GetQueryResults',
            'athena:GetQueryResultsStream',
            'athena:ListQueryExecutions',
            'athena:BatchGetQueryExecution',
          ],
          resources: [`arn:aws:athena:${region}:${account}:workgroup/${athenaWorkgroupName}`],
        }),
        // Athena Workgroup Access
        new iam.PolicyStatement({
          sid: 'AthenaWorkgroupAccess',
          effect: iam.Effect.ALLOW,
          actions: [
            'athena:GetWorkGroup',
            'athena:ListWorkGroups',
          ],
          resources: [`arn:aws:athena:${region}:${account}:workgroup/${athenaWorkgroupName}`],
        }),
        // X-Ray Permissions
        new iam.PolicyStatement({
          sid: 'XRayPermissions',
          effect: iam.Effect.ALLOW,
          actions: [
            'xray:PutTraceSegments',
            'xray:PutTelemetryRecords',
          ],
          resources: ['*'],
          conditions: {
            StringEquals: {
              'aws:RequestedRegion': region,
            },
          },
        }),
      ],
    });

    // Catalog Executor Policy
    this.catalogExecutorPolicy = new iam.ManagedPolicy(this, 'CatalogExecutorPolicy', {
      managedPolicyName: `CatalunyaCatalogExecutorPolicy${environmentName.charAt(0).toUpperCase() + environmentName.slice(1)}`,
      description: `Catalog executor permissions for Catalunya Data Pipeline (${environmentName})`,
      statements: [
        // CloudWatch Logs for catalog functions
        new iam.PolicyStatement({
          sid: 'CloudWatchLogGroups',
          effect: iam.Effect.ALLOW,
          actions: [
            'logs:CreateLogGroup',
            'logs:CreateLogStream',
            'logs:PutLogEvents',
            'logs:DescribeLogGroups',
            'logs:DescribeLogStreams',
          ],
          resources: [
            `arn:aws:logs:${region}:${account}:log-group:/aws/lambda/catalunya-${environmentName}-*catalog*`,
            `arn:aws:logs:${region}:${account}:log-group:/aws/lambda/catalunya-${environmentName}-*catalog*:*`,
          ],
        }),
        // S3 Catalog Bucket Full Access
        new iam.PolicyStatement({
          sid: 'S3CatalogBucketAccess',
          effect: iam.Effect.ALLOW,
          actions: [
            's3:GetBucketLocation',
            's3:ListBucket',
            's3:GetObject',
            's3:PutObject',
            's3:PutObjectAcl',
            's3:DeleteObject',
          ],
          resources: [
            `arn:aws:s3:::${catalogBucketName}`,
            `arn:aws:s3:::${catalogBucketName}/*`,
          ],
        }),
        // Glue Data Catalog Operations
        new iam.PolicyStatement({
          sid: 'GlueDataCatalogOperations',
          effect: iam.Effect.ALLOW,
          actions: [
            'glue:CreateTable',
            'glue:UpdateTable',
            'glue:GetTable',
            'glue:GetTables',
            'glue:DeleteTable',
            'glue:GetDatabase',
            'glue:CreateDatabase',
            'glue:UpdateDatabase',
          ],
          resources: [
            `arn:aws:glue:${region}:${account}:catalog`,
            `arn:aws:glue:${region}:${account}:database/${athenaDatabaseName}`,
            `arn:aws:glue:${region}:${account}:table/${athenaDatabaseName}/*`,
          ],
        }),
        // X-Ray Permissions
        new iam.PolicyStatement({
          sid: 'XRayPermissions',
          effect: iam.Effect.ALLOW,
          actions: [
            'xray:PutTraceSegments',
            'xray:PutTelemetryRecords',
          ],
          resources: ['*'],
          conditions: {
            StringEquals: {
              'aws:RequestedRegion': region,
            },
          },
        }),
      ],
    });

    // Airflow Cross-Account Policy
    this.airflowCrossAccountPolicy = new iam.ManagedPolicy(this, 'AirflowCrossAccountPolicy', {
      managedPolicyName: `CatalunyaAirflowCrossAccountPolicy${environmentName.charAt(0).toUpperCase() + environmentName.slice(1)}`,
      description: `Airflow cross-account permissions for Catalunya Data Pipeline (${environmentName})`,
      statements: [
        new iam.PolicyStatement({
          sid: 'AssumeRolePermissions',
          effect: iam.Effect.ALLOW,
          actions: [
            'sts:AssumeRole',
          ],
          resources: [
            `arn:aws:iam::${account}:role/catalunya-catalog-executor-role-${environmentName}`,
            `arn:aws:iam::${account}:role/catalunya-lambda-extractor-role-${environmentName}`,
            `arn:aws:iam::${account}:role/catalunya-lambda-transformer-role-${environmentName}`,
            `arn:aws:iam::${account}:role/catalunya-mart-role-${environmentName}`,
          ],
        }),
        // Invoke Lambda functions
        new iam.PolicyStatement({
          sid: 'LambdaInvocationPermissions',
          effect: iam.Effect.ALLOW,
          actions: [
            'lambda:InvokeFunction',
            'lambda:GetFunction',
            'lambda:ListFunctions',
          ],
          resources: [
            `arn:aws:lambda:${region}:${account}:function:catalunya-${environmentName}-*`,
          ],
        }),
        // Monitor pipeline status
        new iam.PolicyStatement({
          sid: 'MonitoringPermissions',
          effect: iam.Effect.ALLOW,
          actions: [
            'logs:DescribeLogGroups',
            'logs:DescribeLogStreams',
            'logs:GetLogEvents',
            'cloudwatch:GetMetricStatistics',
            'cloudwatch:ListMetrics',
          ],
          resources: [
            `arn:aws:logs:${region}:${account}:log-group:/aws/lambda/catalunya-${environmentName}-*`,
            `arn:aws:logs:${region}:${account}:log-group:/aws/lambda/catalunya-${environmentName}-*:*`,
          ],
        }),
        // S3 bucket monitoring
        new iam.PolicyStatement({
          sid: 'S3MonitoringPermissions',
          effect: iam.Effect.ALLOW,
          actions: [
            's3:ListBucket',
            's3:GetBucketLocation',
            's3:GetBucketVersioning',
          ],
          resources: [
            `arn:aws:s3:::${bucketName}`,
            `arn:aws:s3:::${catalogBucketName}`,
          ],
        }),
      ],
    });

    // ========================================
    // Lambda Execution Roles
    // ========================================

    // Lambda Extractor Execution Role
    this.extractorExecutionRole = new iam.Role(this, 'ExtractorExecutionRole', {
      roleName: `catalunya-lambda-extractor-role-${environmentName}`,
      description: `Catalunya Data Pipeline - Lambda Extractor Role (${environmentName})`,
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [this.extractorPolicy],
    });

    // Lambda Transformer Execution Role
    this.transformerExecutionRole = new iam.Role(this, 'TransformerExecutionRole', {
      roleName: `catalunya-lambda-transformer-role-${environmentName}`,
      description: `Catalunya Data Pipeline - Lambda Transformer Role (${environmentName})`,
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [this.transformerPolicy],
    });

    // Lambda Mart Execution Role
    this.martExecutionRole = new iam.Role(this, 'MartExecutionRole', {
      roleName: `catalunya-mart-role-${environmentName}`,
      description: `Catalunya Data Pipeline - Mart/DBT Execution Role (${environmentName})`,
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [this.martExecutorPolicy],
    });

    // Lambda Monitoring Execution Role
    this.monitoringExecutionRole = new iam.Role(this, 'MonitoringExecutionRole', {
      roleName: `catalunya-monitoring-role-${environmentName}`,
      description: `Catalunya Data Pipeline - Monitoring Role (${environmentName})`,
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });

    // ========================================
    // Catalog Executor Role
    // ========================================
    this.catalogExecutorRole = new iam.Role(this, 'CatalogExecutorRole', {
      roleName: `catalunya-catalog-executor-role-${environmentName}`,
      description: `Catalog executor role for Catalunya Data Pipeline (${environmentName})`,
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        this.catalogExecutorPolicy,
      ],
    });

    // Apply common tags
    Object.entries(commonTags).forEach(([key, value]) => {
      cdk.Tags.of(this.catalogExecutorRole).add(key, value);
    });

    cdk.Tags.of(this.catalogExecutorRole).add('ServiceType', 'Catalog');
    cdk.Tags.of(this.catalogExecutorRole).add('RoleType', 'Lambda');

    // ========================================
    // Airflow IAM User (Minimal Assumer User)
    // ========================================

    this.airflowUser = new iam.User(this, 'AirflowUser', {
      userName: `dokku-airflow-assumer-${environmentName}`,
      path: '/service-accounts/',
    });

    // Create access key for the user
    this.airflowAccessKey = new iam.AccessKey(this, 'AirflowAccessKey', {
      user: this.airflowUser,
    });

    // Add ONLY AssumeRole permission (minimal permissions principle)
    this.airflowUser.addToPolicy(new iam.PolicyStatement({
      sid: 'AssumeCrossAccountRole',
      effect: iam.Effect.ALLOW,
      actions: ['sts:AssumeRole'],
      resources: [`arn:aws:iam::${account}:role/catalunya-airflow-cross-account-role-${environmentName}`],
      conditions: {
        StringEquals: {
          'sts:ExternalId': `catalunya-${environmentName}-airflow-exec`,
        },
      },
    }));

    // Apply common tags to user
    Object.entries(commonTags).forEach(([key, value]) => {
      cdk.Tags.of(this.airflowUser).add(key, value);
    });

    cdk.Tags.of(this.airflowUser).add('ServiceType', 'Orchestration');
    cdk.Tags.of(this.airflowUser).add('RoleType', 'Assumer');

    // ========================================
    // Airflow Cross-Account Role
    // ========================================

    this.airflowCrossAccountRole = new iam.Role(this, 'AirflowCrossAccountRole', {
      roleName: `catalunya-airflow-cross-account-role-${environmentName}`,
      description: `Airflow cross-account role for Catalunya Data Pipeline (${environmentName})`,
      assumedBy: new iam.ArnPrincipal(this.airflowUser.userArn),
      externalIds: [`catalunya-${environmentName}-airflow-exec`],
      maxSessionDuration: cdk.Duration.minutes(61),
      managedPolicies: [
        this.airflowCrossAccountPolicy,
      ],
    });

    // Apply common tags to cross-account role
    Object.entries(commonTags).forEach(([key, value]) => {
      cdk.Tags.of(this.airflowCrossAccountRole).add(key, value);
    });

    cdk.Tags.of(this.airflowCrossAccountRole).add('ServiceType', 'Orchestration');
    cdk.Tags.of(this.airflowCrossAccountRole).add('RoleType', 'CrossAccount');

    // ========================================
    // Human Data Engineer Role
    // ========================================

    this.dataEngineerRole = new iam.Role(this, 'DataEngineerRole', {
      roleName: 'catalunya-data-engineer-role',
      description: 'Catalunya Data Pipeline - Human Data Engineer Role',
      assumedBy: new iam.AccountRootPrincipal().withConditions({
        Bool: {
          'aws:MultiFactorAuthPresent': 'true',
        },
        StringEquals: {
          'aws:RequestedRegion': region,
        },
      }),
      managedPolicies: [
        // Grant broad permissions for data engineering tasks
        this.extractorPolicy,
        this.transformerPolicy,
        this.martExecutorPolicy,
        iam.ManagedPolicy.fromAwsManagedPolicyName('ReadOnlyAccess'),
      ],
    });

    // ========================================
    // Apply Tags to All IAM Resources
    // ========================================

    // Tag all roles
    Object.entries(commonTags).forEach(([key, value]) => {
      cdk.Tags.of(this.extractorExecutionRole).add(key, value);
      cdk.Tags.of(this.transformerExecutionRole).add(key, value);
      cdk.Tags.of(this.martExecutionRole).add(key, value);
      cdk.Tags.of(this.monitoringExecutionRole).add(key, value);
      cdk.Tags.of(this.dataEngineerRole).add(key, value);
    });

    // Tag all policies
    Object.entries(commonTags).forEach(([key, value]) => {
      cdk.Tags.of(this.extractorPolicy).add(key, value);
      cdk.Tags.of(this.transformerPolicy).add(key, value);
      cdk.Tags.of(this.martExecutorPolicy).add(key, value);
      cdk.Tags.of(this.catalogExecutorPolicy).add(key, value);
      cdk.Tags.of(this.airflowCrossAccountPolicy).add(key, value);
    });

    // Add environment-specific tags
    cdk.Tags.of(this.extractorExecutionRole).add('Service', 'Lambda');
    cdk.Tags.of(this.transformerExecutionRole).add('Service', 'Lambda');
    cdk.Tags.of(this.martExecutionRole).add('Service', 'DBT');
    cdk.Tags.of(this.monitoringExecutionRole).add('Service', 'Lambda');
    cdk.Tags.of(this.dataEngineerRole).add('RoleType', 'Human');
  }

}