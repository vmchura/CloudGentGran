import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import { EnvironmentConfig, ConfigHelper } from './config';

export interface LambdaConstructProps {
    environmentName: string;
    projectName: string;
    config: EnvironmentConfig;
    bucketName: string;
    catalogBucketName: string;
    lambdaPrefix: string;
    account: string;
    region: string;
    extractorExecutionRole: iam.Role;
    transformerExecutionRole: iam.Role;
    martExecutionRole: iam.Role;
    monitoringExecutionRole: iam.Role;
}

interface LambdaFunctionProps {
    environmentName: string;
    projectName: string;
    config: EnvironmentConfig;
    bucketName: string;
    catalogBucketName: string,
    lambdaPrefix: string;
    account: string;
    region: string;
    executionRole: iam.Role;
}

export class LambdaConstruct extends Construct {
    public readonly apiExtractorLambda: lambda.Function;
    public readonly populationMunicipalGreater65ApiExtractorLambda: lambda.Function;
    public readonly socialServicesTransformerLambda: lambda.Function;
    public readonly populationMunicipalGreater65Transformer: lambda.Function;
    public readonly populationMunicipalGreater65Mart: lambda.Function;

    constructor(scope: Construct, id: string, props: LambdaConstructProps) {
        super(scope, id);

        const {
            environmentName,
            projectName,
            config,
            bucketName,
            catalogBucketName,
            lambdaPrefix,
            account,
            region
        } = props;

        // Create API Extractor Lambda
        this.apiExtractorLambda = this.createApiExtractorLambda({
            environmentName,
            projectName,
            config,
            bucketName,
            catalogBucketName,
            lambdaPrefix,
            account,
            region,
            executionRole: props.extractorExecutionRole
        });

        // Create Social Services Transformer Lambda
        this.socialServicesTransformerLambda = this.createSocialServicesTransformerLambda({
            environmentName,
            projectName,
            config,
            bucketName,
            catalogBucketName,
            lambdaPrefix,
            account,
            region,
            executionRole: props.transformerExecutionRole
        });

        this.populationMunicipalGreater65ApiExtractorLambda = this.createApiExtractorLambdaPopulationGreater65({
            environmentName,
            projectName,
            config,
            bucketName,
            catalogBucketName,
            lambdaPrefix,
            account,
            region,
            executionRole: props.extractorExecutionRole
        });

        this.populationMunicipalGreater65Transformer = this.createPopulationMunicipalGreater65Transformer({
            environmentName,
            projectName,
            config,
            bucketName,
            catalogBucketName,
            lambdaPrefix,
            account,
            region,
            executionRole: props.transformerExecutionRole
        });

        this.populationMunicipalGreater65Mart = this.createPopulationMunicipalGreater65Mart({
            environmentName,
            projectName,
            config,
            bucketName,
            catalogBucketName,
            lambdaPrefix,
            account,
            region,
            executionRole: props.martExecutionRole
        });
    }

    /**
     * Gets the appropriate Python Lambda code, skipping bundling for tests
     */
    private getPythonLambdaCode(extractor_directory: string): lambda.Code {
        const isTest = process.env.NODE_ENV === 'test' ||
            process.env.CDK_DEFAULT_ACCOUNT === '123456789012';

        if (isTest) {
            // Skip bundling for tests - just use the source directory
            console.log('🧪 Skipping Python bundling for tests');
            return lambda.Code.fromAsset(`../lambda/extractors/${extractor_directory}`);
        } else {
            // Use bundling for real deployments
            console.log('📦 Using Python bundling for deployment');
            return lambda.Code.fromAsset(`../lambda/extractors/${extractor_directory}`, {
                bundling: {
                    image: lambda.Runtime.PYTHON_3_9.bundlingImage,
                    command: [
                        'bash', '-c', [
                            'pip install -r requirements.txt -t /asset-output',
                            'cp -au . /asset-output'
                        ].join(' && ')
                    ],
                },
            });
        }
    }

    /**
     * Creates Lambda infrastructure including the API extractor function with proper IAM roles.
     * Scheduling and orchestration handled by Airflow.
     */
    private createApiExtractorLambda(props: LambdaFunctionProps): lambda.Function {
        const {
            environmentName,
            projectName,
            config,
            bucketName,
            catalogBucketName,
            lambdaPrefix,
            account,
            region
        } = props;

        // ========================================
        // IAM Role for Lambda
        // ========================================

        // Use existing IAM role or create inline permissions
        // Use the execution role from props
        const lambdaRole = props.executionRole;

        // ========================================
        // Lambda Function
        // ========================================

        const apiExtractorLambda = new lambda.Function(this, 'social_services_ApiExtractorLambda', {
            functionName: `${lambdaPrefix}-social_services`,
            runtime: lambda.Runtime.PYTHON_3_13,
            handler: 'api_extractor.lambda_handler',
            code: this.getPythonLambdaCode('social_services'),
            timeout: cdk.Duration.seconds(config.lambdaTimeout),
            memorySize: config.lambdaMemory,
            role: lambdaRole,
            environment: {
                BUCKET_NAME: bucketName,
                SEMANTIC_IDENTIFIER: 'social_services',
                DATASET_IDENTIFIER: 'ivft-vegh',
                ENVIRONMENT: environmentName,
                REGION: region
            },
            description: `API Extractor Lambda for ${environmentName} environment - Orchestrated by Airflow`,
        });

        // ========================================
        // Tags and Outputs
        // ========================================

        const commonTags = ConfigHelper.getCommonTags(environmentName);
        Object.entries(commonTags).forEach(([key, value]) => {
            cdk.Tags.of(apiExtractorLambda).add(key, value);
        });

        // Additional Lambda tags
        cdk.Tags.of(apiExtractorLambda).add('Purpose', 'DataExtraction');
        cdk.Tags.of(apiExtractorLambda).add('Layer', 'Ingestion');
        cdk.Tags.of(apiExtractorLambda).add('DataSource', 'PublicAPI');

        // Lambda outputs
        new cdk.CfnOutput(this, 'ApiExtractorLambdaArn', {
            value: apiExtractorLambda.functionArn,
            description: 'ARN of the API Extractor Lambda function',
            exportName: `${projectName}-ApiExtractorLambdaArn`,
        });

        new cdk.CfnOutput(this, 'ApiExtractorLambdaName', {
            value: apiExtractorLambda.functionName,
            description: 'Name of the API Extractor Lambda function',
            exportName: `${projectName}-ApiExtractorLambdaName`,
        });

        return apiExtractorLambda;
    }

    private createApiExtractorLambdaPopulationGreater65(props: LambdaFunctionProps): lambda.Function {
        const {
            environmentName,
            projectName,
            config,
            bucketName,
            catalogBucketName,
            lambdaPrefix,
            account,
            region
        } = props;

        const lambdaRole = props.executionRole;

        const apiExtractorLambda = new lambda.Function(this, 'population_municipal_greater_65_ApiExtractorLambda', {
            functionName: `${lambdaPrefix}-population_municipal_greater_65`,
            runtime: lambda.Runtime.PYTHON_3_13,
            handler: 'api_extractor.lambda_handler',
            code: this.getPythonLambdaCode('population_municipal_greater_65'),
            timeout: cdk.Duration.seconds(config.lambdaTimeout),
            memorySize: config.lambdaMemory,
            role: lambdaRole,
            environment: {
                BUCKET_NAME: bucketName,
                SEMANTIC_IDENTIFIER: 'population_municipal_greater_65',
            },
            description: `API Extractor Lambda Population Municipal Greater 65 for ${environmentName} environment - Orchestrated by Airflow`,
        });

        const commonTags = ConfigHelper.getCommonTags(environmentName);
        Object.entries(commonTags).forEach(([key, value]) => {
            cdk.Tags.of(apiExtractorLambda).add(key, value);
        });

        cdk.Tags.of(apiExtractorLambda).add('Purpose', 'DataExtraction');
        cdk.Tags.of(apiExtractorLambda).add('Layer', 'Ingestion');
        cdk.Tags.of(apiExtractorLambda).add('DataSource', 'PublicAPI');

        new cdk.CfnOutput(this, 'PopulationGreater65ApiExtractorLambdaArn', {
            value: apiExtractorLambda.functionArn,
            description: 'ARN of the PopulationGreater65 API Extractor Lambda function',
            exportName: `${projectName}-APopulationGreater65piExtractorLambdaArn`,
        });

        new cdk.CfnOutput(this, 'PopulationGreater65ApiExtractorLambdaName', {
            value: apiExtractorLambda.functionName,
            description: 'Name of the PopulationGreater65 API Extractor Lambda function',
            exportName: `${projectName}-PopulationGreater65ApiExtractorLambdaName`,
        });

        return apiExtractorLambda;
    }

    /**
     * Creates Transformer Lambda infrastructure including the social services transformer function
     * with proper IAM roles. Orchestration handled by Airflow.
     */
    private createSocialServicesTransformerLambda(props: LambdaFunctionProps): lambda.Function {
        const {
            environmentName,
            projectName,
            config,
            bucketName,
            catalogBucketName,
            lambdaPrefix,
            account,
            region
        } = props;

        // ========================================
        // IAM Role for Transformer Lambda
        // ========================================

        let transformerRole: iam.IRole = props.executionRole;


        // ========================================
        // Social Services Transformer Lambda (Rust)
        // ========================================

        const socialServicesTransformerLambda = new lambda.Function(this, 'SocialServicesTransformerLambda', {
            functionName: `${lambdaPrefix}-social-services-transformer`,
            runtime: lambda.Runtime.PROVIDED_AL2023,
            handler: 'bootstrap',
            code: lambda.Code.fromAsset('../target/social_services'),
            timeout: cdk.Duration.seconds(config.lambdaTimeout),
            memorySize: config.lambdaMemory,
            role: transformerRole,
            environment: {
                BUCKET_NAME: bucketName,
                CATALOG_BUCKET_NAME: catalogBucketName,
                SEMANTIC_IDENTIFIER: 'social_services',
                ENVIRONMENT: environmentName,
                REGION: region
            },
            description: `Social Services Transformer Lambda (Rust) for ${environmentName} environment - Orchestrated by Airflow`,
        });

        // ========================================
        // Tags and Outputs
        // ========================================

        const commonTags = ConfigHelper.getCommonTags(environmentName);
        Object.entries(commonTags).forEach(([key, value]) => {
            cdk.Tags.of(socialServicesTransformerLambda).add(key, value);
        });

        // Additional transformer tags
        cdk.Tags.of(socialServicesTransformerLambda).add('Purpose', 'DataTransformation');
        cdk.Tags.of(socialServicesTransformerLambda).add('Layer', 'Processing');
        cdk.Tags.of(socialServicesTransformerLambda).add('DataFlow', 'LandingToStaging');

        // Transformer outputs
        new cdk.CfnOutput(this, 'SocialServicesTransformerLambdaArn', {
            value: socialServicesTransformerLambda.functionArn,
            description: 'ARN of the Social Services Transformer Lambda function',
            exportName: `${projectName}-SocialServicesTransformerLambdaArn`,
        });

        new cdk.CfnOutput(this, 'SocialServicesTransformerLambdaName', {
            value: socialServicesTransformerLambda.functionName,
            description: 'Name of the Social Services Transformer Lambda function',
            exportName: `${projectName}-SocialServicesTransformerLambdaName`,
        });

        return socialServicesTransformerLambda;
    }

    private createPopulationMunicipalGreater65Transformer(props: LambdaFunctionProps): lambda.Function {
        const {
            environmentName,
            projectName,
            config,
            bucketName,
            catalogBucketName,
            lambdaPrefix,
            account,
            region
        } = props;

        let transformerRole: iam.IRole = props.executionRole;

        const lambdaFunction = new lambda.Function(this, 'PopulationMunicipalGreater65TransformerLambda', {
            functionName: `${lambdaPrefix}-population_municipal_greater_65-transformer`,
            runtime: lambda.Runtime.PROVIDED_AL2023,
            handler: 'bootstrap',
            code: lambda.Code.fromAsset('../target/population_municipal_greater_65'),
            timeout: cdk.Duration.seconds(config.lambdaTimeout),
            memorySize: config.lambdaMemory,
            role: transformerRole,
            environment: {
                BUCKET_NAME: bucketName,
                CATALOG_BUCKET_NAME: catalogBucketName,
                SEMANTIC_IDENTIFIER: 'population_municipal_greater_65',
                ENVIRONMENT: environmentName,
                REGION: region
            },
            description: `Population Municipal Greater 65 ${environmentName} environment - Orchestrated by Airflow`,
        });
        const commonTags = ConfigHelper.getCommonTags(environmentName);
        Object.entries(commonTags).forEach(([key, value]) => {
            cdk.Tags.of(lambdaFunction).add(key, value);
        });

        // Additional transformer tags
        cdk.Tags.of(lambdaFunction).add('Purpose', 'DataTransformation');
        cdk.Tags.of(lambdaFunction).add('Layer', 'Processing');
        cdk.Tags.of(lambdaFunction).add('DataFlow', 'LandingToStaging');

        // Transformer outputs
        new cdk.CfnOutput(this, 'PopulationMunicipalGreater65TransformerLambdaArn', {
            value: lambdaFunction.functionArn,
            description: 'ARN of the Population Municipal Greater 65 Transformer Lambda function',
            exportName: `${projectName}-PopulationMunicipalGreater65TransformerLambdaArn`,
        });

        new cdk.CfnOutput(this, 'PopulationMunicipalGreater65TransformerLambdaName', {
            value: lambdaFunction.functionName,
            description: 'Name of the Population Municipal Greater 65 Lambda function',
            exportName: `${projectName}-PopulationMunicipalGreater65TransformerLambdaName`,
        });

        return lambdaFunction;

    }

    private createPopulationMunicipalGreater65Mart(props: LambdaFunctionProps): lambda.Function {
        const {
            environmentName,
            projectName,
            config,
            bucketName,
            catalogBucketName,
            lambdaPrefix,
            account,
            region
        } = props;
        let transformerRole: iam.IRole = props.executionRole;

        const lambdaFunction = new lambda.Function(this, 'PopulationMunicipalGreater65MartLambda', {
            functionName: `${lambdaPrefix}-population_municipal_greater_65-mart`,
            runtime: lambda.Runtime.PROVIDED_AL2023,
            handler: 'bootstrap',
            code: lambda.Code.fromAsset('../target/population_municipal_greater_65_mart'),
            timeout: cdk.Duration.seconds(config.lambdaTimeout),
            memorySize: config.lambdaMemory,
            role: transformerRole,
            environment: {
                BUCKET_NAME: bucketName,
                CATALOG_BUCKET_NAME: catalogBucketName,
                SEMANTIC_IDENTIFIER: 'population_municipal_greater_65',
                ENVIRONMENT: environmentName,
                REGION: region
            },
            description: `Population Municipal Greater 65 Mart ${environmentName} environment - Orchestrated by Airflow`,
        });
        const commonTags = ConfigHelper.getCommonTags(environmentName);
        Object.entries(commonTags).forEach(([key, value]) => {
            cdk.Tags.of(lambdaFunction).add(key, value);
        });

        // Additional transformer tags
        cdk.Tags.of(lambdaFunction).add('Purpose', 'DataRefinement');
        cdk.Tags.of(lambdaFunction).add('Layer', 'Processing');
        cdk.Tags.of(lambdaFunction).add('DataFlow', 'StagingToMart');

        // Transformer outputs
        new cdk.CfnOutput(this, 'PopulationMunicipalGreater65MartLambdaArn', {
            value: lambdaFunction.functionArn,
            description: 'ARN of the Population Municipal Greater 65 Mart Lambda function',
            exportName: `${projectName}-PopulationMunicipalGreater65MartLambdaArn`,
        });

        new cdk.CfnOutput(this, 'PopulationMunicipalGreater65MartLambdaName', {
            value: lambdaFunction.functionName,
            description: 'Name of the Population Municipal Greater 65 Lambda Mart function',
            exportName: `${projectName}-PopulationMunicipalGreater65MartLambdaName`,
        });

        return lambdaFunction;

    }
}