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
  githubRepo?: string;
}

export class IamConstruct extends Construct {
  // Lambda execution roles
  public readonly extractorExecutionRole: iam.Role;
  public readonly transformerExecutionRole: iam.Role;
  public readonly martExecutionRole: iam.Role;
  public readonly monitoringExecutionRole: iam.Role;

  // GitHub OIDC roles
  public readonly githubDeploymentRole: iam.Role;
  public readonly githubOidcProvider: iam.OpenIdConnectProvider;

  // Human roles
  public readonly dataEngineerRole: iam.Role;

  // IAM policies
  public readonly extractorPolicy: iam.ManagedPolicy;
  public readonly transformerPolicy: iam.ManagedPolicy;
  public readonly martExecutorPolicy: iam.ManagedPolicy;
  public readonly deploymentPolicy: iam.ManagedPolicy;

  constructor(scope: Construct, id: string, props: IamConstructProps) {
    super(scope, id);

    const { environmentName, projectName, config, account, region, bucketName,
            athenaResultsBucketName, athenaDatabaseName, athenaWorkgroupName } = props;

    const githubRepo = props.githubRepo || 'vmchura/CloudGentGran';

    // Common tags for all IAM resources
    const commonTags = ConfigHelper.getCommonTags(environmentName);

    // ========================================
    // GitHub OIDC Provider (if not exists)
    // ========================================
    this.githubOidcProvider = new iam.OpenIdConnectProvider(this, 'GitHubOIDCProvider', {
      url: 'https://token.actions.githubusercontent.com',
      clientIds: ['sts.amazonaws.com'],
      thumbprints: ['6938fd4d98bab03faadb97b34396831e3780aea1'], // GitHub's thumbprint
    });

    cdk.Tags.of(this.githubOidcProvider).add('Project', commonTags.Project);

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

    // Deployment Policy for GitHub Actions
    this.deploymentPolicy = new iam.ManagedPolicy(this, 'DeploymentPolicy', {
      managedPolicyName: 'CatalunyaDeploymentPolicy',
      description: 'Deployment permissions for Catalunya Data Pipeline CDK stacks',
      statements: [
        // CloudFormation Stack Operations
        new iam.PolicyStatement({
          sid: 'CloudFormationStackOps',
          effect: iam.Effect.ALLOW,
          actions: [
            'cloudformation:CreateStack',
            'cloudformation:UpdateStack',
            'cloudformation:DeleteStack',
            'cloudformation:DescribeStacks',
            'cloudformation:GetTemplate',
            'cloudformation:CreateChangeSet',
            'cloudformation:ExecuteChangeSet',
            'cloudformation:DescribeChangeSet',
            'cloudformation:DescribeStackEvents',
            'cloudformation:GetTemplateSummary',
            'cloudformation:DescribeStackResources',
          ],
          resources: [
            `arn:aws:cloudformation:${region}:${account}:stack/CatalunyaDataStack-dev/*`,
            `arn:aws:cloudformation:${region}:${account}:stack/CatalunyaDataStack-prod/*`,
            `arn:aws:cloudformation:${region}:${account}:stack/CDKToolkit/*`,
          ],
        }),
        // CloudFormation List Operations
        new iam.PolicyStatement({
          sid: 'CloudFormationList',
          effect: iam.Effect.ALLOW,
          actions: ['cloudformation:ListStacks'],
          resources: ['*'],
          conditions: {
            StringEquals: {
              'aws:RequestedRegion': region,
            },
          },
        }),
        // S3 Project Buckets Management
        new iam.PolicyStatement({
          sid: 'S3ProjectBuckets',
          effect: iam.Effect.ALLOW,
          actions: [
            's3:CreateBucket',
            's3:DeleteBucket',
            's3:GetBucketLocation',
            's3:GetBucketVersioning',
            's3:GetBucketEncryption',
            's3:GetBucketPublicAccessBlock',
            's3:GetBucketNotification',
            's3:GetBucketTagging',
            's3:PutBucketVersioning',
            's3:PutBucketEncryption',
            's3:PutBucketPublicAccessBlock',
            's3:PutBucketNotification',
            's3:PutBucketTagging',
            's3:ListBucket',
          ],
          resources: [
            'arn:aws:s3:::catalunya-data-*',
            'arn:aws:s3:::cdk-hnb659fds-*',
          ],
        }),
        // S3 Project Objects Management
        new iam.PolicyStatement({
          sid: 'S3ProjectObjects',
          effect: iam.Effect.ALLOW,
          actions: [
            's3:GetObject',
            's3:PutObject',
            's3:DeleteObject',
            's3:GetObjectVersion',
            's3:DeleteObjectVersion',
          ],
          resources: [
            'arn:aws:s3:::catalunya-data-*/*',
            'arn:aws:s3:::cdk-hnb659fds-*/*',
          ],
        }),
        // IAM Pass Roles
        new iam.PolicyStatement({
          sid: 'IAMPassRoles',
          effect: iam.Effect.ALLOW,
          actions: ['iam:GetRole', 'iam:PassRole'],
          resources: [
            `arn:aws:iam::${account}:role/cdk-*`,
            `arn:aws:iam::${account}:role/*S3AutoDeleteObjectsCustomResourceProviderRole*`,
            `arn:aws:iam::${account}:role/catalunya-*`,
          ],
        }),
        // Lambda Project Functions Management
        new iam.PolicyStatement({
          sid: 'LambdaProjectFunctions',
          effect: iam.Effect.ALLOW,
          actions: [
            'lambda:CreateFunction',
            'lambda:DeleteFunction',
            'lambda:GetFunction',
            'lambda:UpdateFunctionCode',
            'lambda:UpdateFunctionConfiguration',
            'lambda:InvokeFunction',
            'lambda:TagResource',
            'lambda:UntagResource',
            'lambda:ListTags',
            'lambda:AddPermission',
            'lambda:RemovePermission',
            'lambda:GetPolicy',
          ],
          resources: [
            `arn:aws:lambda:${region}:${account}:function:*S3AutoDeleteObjectsCustomResourceProvider*`,
            `arn:aws:lambda:${region}:${account}:function:CatalunyaDataStack-*`,
            `arn:aws:lambda:${region}:${account}:function:catalunya-*`,
          ],
        }),
        // Glue Data Catalog Minimal Management
        new iam.PolicyStatement({
          sid: 'GlueDataCatalogMinimal',
          effect: iam.Effect.ALLOW,
          actions: [
            'glue:CreateDatabase',
            'glue:DeleteDatabase',
            'glue:GetDatabase',
            'glue:UpdateDatabase',
            'glue:TagResource',
            'glue:UntagResource',
          ],
          resources: [
            `arn:aws:glue:${region}:${account}:catalog`,
            `arn:aws:glue:${region}:${account}:database/catalunya_data_*`,
          ],
        }),
        // Athena Workgroup Minimal Management
        new iam.PolicyStatement({
          sid: 'AthenaWorkgroupMinimal',
          effect: iam.Effect.ALLOW,
          actions: [
            'athena:CreateWorkGroup',
            'athena:DeleteWorkGroup',
            'athena:GetWorkGroup',
            'athena:UpdateWorkGroup',
            'athena:TagResource',
            'athena:UntagResource',
          ],
          resources: [`arn:aws:athena:${region}:${account}:workgroup/catalunya-workgroup-*`],
        }),
        // CDK Bootstrap SSM Parameters
        new iam.PolicyStatement({
          sid: 'CDKBootstrapSSM',
          effect: iam.Effect.ALLOW,
          actions: [
            'ssm:GetParameter',
            'ssm:GetParameters',
            'ssm:PutParameter',
            'ssm:DeleteParameter',
          ],
          resources: [`arn:aws:ssm:${region}:${account}:parameter/cdk-bootstrap*`],
        }),
        // IAM CDK Role Management
        new iam.PolicyStatement({
          sid: 'IAMCDKRoleManagement',
          effect: iam.Effect.ALLOW,
          actions: [
            'iam:CreateRole',
            'iam:DeleteRole',
            'iam:PutRolePolicy',
            'iam:DeleteRolePolicy',
            'iam:GetRole',
            'iam:GetRolePolicy',
            'iam:AttachRolePolicy',
            'iam:DetachRolePolicy',
            'iam:TagRole',
            'iam:UntagRole',
          ],
          resources: [`arn:aws:iam::${account}:role/cdk-*`],
        }),
        // STS Assume Role for CDK
        new iam.PolicyStatement({
          sid: 'STSAssumeRole',
          effect: iam.Effect.ALLOW,
          actions: ['sts:AssumeRole'],
          resources: [`arn:aws:iam::${account}:role/cdk-*`],
        }),
        // ECR Repository Management
        new iam.PolicyStatement({
          sid: 'ECRRepositoryManagement',
          effect: iam.Effect.ALLOW,
          actions: [
            'ecr:DeleteRepository',
            'ecr:CreateRepository',
            'ecr:DescribeRepositories',
            'ecr:PutLifecyclePolicy',
            'ecr:SetRepositoryPolicy',
            'ecr:TagResource',
          ],
          resources: [`arn:aws:ecr:${region}:${account}:repository/cdk*`],
          conditions: {
            StringEquals: {
              'aws:RequestedRegion': region,
            },
          },
        }),
        // CDK Bootstrap Bucket Operations
        new iam.PolicyStatement({
          sid: 'AllowCDKBootstrapBucket',
          effect: iam.Effect.ALLOW,
          actions: [
            's3:GetBucketLocation',
            's3:GetBucketVersioning',
            's3:PutBucketVersioning',
            's3:GetBucketEncryption',
            's3:PutBucketEncryption',
            's3:GetBucketPublicAccessBlock',
            's3:PutBucketPublicAccessBlock',
          ],
          resources: ['arn:aws:s3:::cdk-hnb659fds-*'],
        }),
        // Resource Tagging
        new iam.PolicyStatement({
          sid: 'AllowProjectTagging',
          effect: iam.Effect.ALLOW,
          actions: [
            'tag:GetResources',
            'tag:TagResources',
            'tag:UntagResources',
          ],
          resources: ['*'],
          conditions: {
            StringEquals: {
              'aws:RequestedRegion': region,
            },
            StringLike: {
              'aws:ResourceTag:Project': 'CatalunyaDataPipeline',
            },
          },
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
    // GitHub OIDC Deployment Role
    // ========================================

    this.githubDeploymentRole = new iam.Role(this, 'GitHubDeploymentRole', {
      roleName: `catalunya-deployment-role-${environmentName}`,
      description: `Catalunya Data Pipeline - GitHub Actions Role (${environmentName})`,
      assumedBy: new iam.WebIdentityPrincipal(
        this.githubOidcProvider.openIdConnectProviderArn,
        {
          StringLike: {
            'token.actions.githubusercontent.com:sub': `repo:${githubRepo}:*`,
          },
          StringEquals: {
            'token.actions.githubusercontent.com:aud': 'sts.amazonaws.com',
          },
        }
      ),
      managedPolicies: [this.deploymentPolicy],
    });

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
      cdk.Tags.of(this.githubDeploymentRole).add(key, value);
      cdk.Tags.of(this.dataEngineerRole).add(key, value);
    });

    // Tag all policies
    Object.entries(commonTags).forEach(([key, value]) => {
      cdk.Tags.of(this.extractorPolicy).add(key, value);
      cdk.Tags.of(this.transformerPolicy).add(key, value);
      cdk.Tags.of(this.martExecutorPolicy).add(key, value);
      cdk.Tags.of(this.deploymentPolicy).add(key, value);
    });

    // Add environment-specific tags
    cdk.Tags.of(this.extractorExecutionRole).add('Service', 'Lambda');
    cdk.Tags.of(this.transformerExecutionRole).add('Service', 'Lambda');
    cdk.Tags.of(this.martExecutionRole).add('Service', 'DBT');
    cdk.Tags.of(this.monitoringExecutionRole).add('Service', 'Lambda');
    cdk.Tags.of(this.githubDeploymentRole).add('Service', 'GitHubActions');
    cdk.Tags.of(this.dataEngineerRole).add('RoleType', 'Human');
  }

  /**
   * Get the Lambda execution role for a specific service type
   */
  public getLambdaExecutionRole(serviceType: 'extractor' | 'transformer' | 'mart' | 'monitoring'): iam.Role {
    switch (serviceType) {
      case 'extractor':
        return this.extractorExecutionRole;
      case 'transformer':
        return this.transformerExecutionRole;
      case 'mart':
        return this.martExecutionRole;
      case 'monitoring':
        return this.monitoringExecutionRole;
      default:
        throw new Error(`Unknown service type: ${serviceType}`);
    }
  }

  /**
   * Grant additional permissions to a Lambda execution role
   */
  public grantAdditionalPermissions(
    serviceType: 'extractor' | 'transformer' | 'mart' | 'monitoring',
    ...permissions: iam.PolicyStatement[]
  ): void {
    const role = this.getLambdaExecutionRole(serviceType);

    permissions.forEach((permission, index) => {
      role.addToPolicy(permission);
    });
  }

  /**
   * Create a custom managed policy for specific use cases
   */
  public createCustomPolicy(
    policyName: string,
    description: string,
    statements: iam.PolicyStatement[]
  ): iam.ManagedPolicy {
    return new iam.ManagedPolicy(this, policyName, {
      managedPolicyName: policyName,
      description,
      statements,
    });
  }
}