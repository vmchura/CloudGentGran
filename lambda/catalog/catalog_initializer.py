import json
import boto3
import pandas as pd
import os
from typing import Dict, List, Any
from datetime import datetime
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Lambda function to initialize and manage catalog dimension tables.

    This function can:
    1. Initialize dimension tables in the catalog bucket
    2. Create Glue table definitions
    3. Update existing tables
    4. Sync with AWS Glue Catalog for compatibility

    Event structure:
    {
        "action": "init_table" | "update_table" | "list_tables" | "create_default_tables",
        "table_name": "institution_types" | "territorial_hierarchy",
        "data": [...] (for init/update operations)
    }
    """

    try:
        # Get environment variables
        catalog_bucket = os.environ['CATALOG_BUCKET_NAME']
        data_bucket = os.environ['DATA_BUCKET_NAME']
        glue_database = os.environ['GLUE_DATABASE_NAME']
        environment = os.environ['ENVIRONMENT']
        region = os.environ['REGION']

        # Initialize AWS clients
        s3_client = boto3.client('s3')
        glue_client = boto3.client('glue')

        # Parse event
        action = event.get('action', 'list_tables')
        table_name = event.get('table_name')
        table_data = event.get('data', [])

        logger.info(f"Processing action: {action} for table: {table_name}")

        if action == 'init_table':
            response = initialize_dimension_table(
                s3_client, glue_client, catalog_bucket, glue_database,
                table_name, table_data, environment
            )
        elif action == 'update_table':
            response = update_dimension_table(
                s3_client, glue_client, catalog_bucket, glue_database,
                table_name, table_data, environment
            )
        elif action == 'list_tables':
            response = list_catalog_tables(s3_client, catalog_bucket)
        elif action == 'create_default_tables':
            response = create_default_dimension_tables(
                s3_client, glue_client, catalog_bucket, glue_database, environment
            )
        else:
            response = {
                'statusCode': 400,
                'body': json.dumps(f'Unknown action: {action}')
            }

        logger.info(f"Action completed successfully: {action}")
        return response

    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }


def initialize_dimension_table(s3_client, glue_client, bucket_name: str,
                               database_name: str, table_name: str,
                               data: List[Dict], environment: str) -> Dict:
    """Initialize a new dimension table in the catalog."""

    try:
        # Create DataFrame
        df = pd.DataFrame(data)

        if df.empty:
            raise ValueError(f"No data provided for table {table_name}")

        # Add metadata columns
        df['created_at'] = datetime.utcnow().isoformat()
        df['updated_at'] = datetime.utcnow().isoformat()
        df['environment'] = environment

        # Define S3 path


        # Save to S3 as Parquet
        s3_key = f"dimension_tables/{table_name}/data.parquet"
        local_path = f"/tmp/{table_name}.parquet"
        df.to_parquet(local_path, engine="fastparquet", index=False)

        s3_client.upload_file(
            local_path,
            bucket_name,
            s3_key,
            ExtraArgs={
                "ContentType": "application/octet-stream",
                "Metadata": {
                    "table_name": table_name,
                    "environment": environment,
                    "record_count": str(len(df)),
                    "created_at": datetime.utcnow().isoformat()
                }
            }
        )

        # Create Glue table definition
        create_glue_table(glue_client, database_name, table_name, bucket_name, s3_key, df)

        logger.info(f"Initialized table {table_name} with {len(df)} records")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Table {table_name} initialized successfully',
                'record_count': len(df),
                's3_location': f's3://{bucket_name}/{s3_key}',
                'table_name': table_name
            })
        }

    except Exception as e:
        logger.error(f"Error initializing table {table_name}: {str(e)}")
        raise


def update_dimension_table(s3_client, glue_client, bucket_name: str,
                           database_name: str, table_name: str,
                           data: List[Dict], environment: str) -> Dict:
    """Update an existing dimension table."""

    try:
        # Create DataFrame
        df = pd.DataFrame(data)

        if df.empty:
            raise ValueError(f"No data provided for table {table_name}")

        # Add metadata columns
        df['updated_at'] = datetime.utcnow().isoformat()
        df['environment'] = environment

        # Try to preserve created_at from existing data
        try:
            existing_key = f"dimension_tables/{table_name}/data.parquet"
            existing_obj = s3_client.get_object(Bucket=bucket_name, Key=existing_key)
            existing_df = pd.read_parquet(existing_obj['Body'])

            # If we have existing created_at, preserve it
            if 'created_at' in existing_df.columns and not existing_df.empty:
                df['created_at'] = existing_df['created_at'].iloc[0]
            else:
                df['created_at'] = datetime.utcnow().isoformat()

        except Exception:
            # If no existing data, set created_at to now
            df['created_at'] = datetime.utcnow().isoformat()

        # Create versioned backup
        backup_key = f"dimension_tables/{table_name}/versions/{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.parquet"

        # Save new version
        s3_key = f"dimension_tables/{table_name}/data.parquet"
        parquet_buffer = df.to_parquet(index=False)

        # Upload new data
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=parquet_buffer,
            ContentType='application/octet-stream',
            Metadata={
                'table_name': table_name,
                'environment': environment,
                'record_count': str(len(df)),
                'updated_at': datetime.utcnow().isoformat()
            }
        )

        # Update Glue table
        update_glue_table(glue_client, database_name, table_name, bucket_name, s3_key, df)

        logger.info(f"Updated table {table_name} with {len(df)} records")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Table {table_name} updated successfully',
                'record_count': len(df),
                's3_location': f's3://{bucket_name}/{s3_key}',
                'table_name': table_name
            })
        }

    except Exception as e:
        logger.error(f"Error updating table {table_name}: {str(e)}")
        raise


def list_catalog_tables(s3_client, bucket_name: str) -> Dict:
    """List all dimension tables in the catalog."""

    try:
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix='dimension_tables/',
            Delimiter='/'
        )

        tables = []
        if 'CommonPrefixes' in response:
            for prefix in response['CommonPrefixes']:
                table_name = prefix['Prefix'].split('/')[-2]

                # Get table metadata
                try:
                    obj_response = s3_client.head_object(
                        Bucket=bucket_name,
                        Key=f"dimension_tables/{table_name}/data.parquet"
                    )

                    tables.append({
                        'table_name': table_name,
                        'last_modified': obj_response['LastModified'].isoformat(),
                        'size_bytes': obj_response['ContentLength'],
                        'record_count': obj_response.get('Metadata', {}).get('record_count', 'unknown'),
                        's3_location': f's3://{bucket_name}/dimension_tables/{table_name}/data.parquet'
                    })
                except Exception as e:
                    logger.warning(f"Could not get metadata for table {table_name}: {str(e)}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'tables': tables,
                'table_count': len(tables)
            })
        }

    except Exception as e:
        logger.error(f"Error listing tables: {str(e)}")
        raise


def create_default_dimension_tables(s3_client, glue_client, bucket_name: str,
                                    database_name: str, environment: str) -> Dict:
    """Create default dimension tables for Catalunya data."""

    try:
        tables_created = []

        # 1. Institution Types
        institution_types_data = [
            {"id": 1, "code": "HOSPITAL", "name": "Hospital", "category": "healthcare", "description": "Medical care facility"},
            {"id": 2, "code": "CLINIC", "name": "Clinic", "category": "healthcare", "description": "Outpatient medical facility"},
            {"id": 3, "code": "PHARMACY", "name": "Pharmacy", "category": "healthcare", "description": "Medication dispensary"},
            {"id": 4, "code": "SCHOOL", "name": "School", "category": "education", "description": "Educational institution"},
            {"id": 5, "code": "UNIVERSITY", "name": "University", "category": "education", "description": "Higher education institution"},
            {"id": 6, "code": "LIBRARY", "name": "Library", "category": "education", "description": "Public library"},
            {"id": 7, "code": "SOCIAL_CENTER", "name": "Social Center", "category": "social_services", "description": "Community social services"},
            {"id": 8, "code": "ELDERLY_CENTER", "name": "Elderly Center", "category": "social_services", "description": "Services for elderly population"},
            {"id": 9, "code": "YOUTH_CENTER", "name": "Youth Center", "category": "social_services", "description": "Services for youth population"},
            {"id": 10, "code": "SPORTS_CENTER", "name": "Sports Center", "category": "recreation", "description": "Sports and recreation facility"}
        ]

        result = initialize_dimension_table(
            s3_client, glue_client, bucket_name, database_name,
            'institution_types', institution_types_data, environment
        )
        tables_created.append('institution_types')

        # 2. Territorial Hierarchy
        territorial_hierarchy_data = [
            {"id": 1, "code": "CAT", "name": "Catalunya", "level": "region", "parent_id": None, "parent_code": None},
            {"id": 2, "code": "BCN", "name": "Barcelona", "level": "province", "parent_id": 1, "parent_code": "CAT"},
            {"id": 3, "code": "GIR", "name": "Girona", "level": "province", "parent_id": 1, "parent_code": "CAT"},
            {"id": 4, "code": "LLE", "name": "Lleida", "level": "province", "parent_id": 1, "parent_code": "CAT"},
            {"id": 5, "code": "TAR", "name": "Tarragona", "level": "province", "parent_id": 1, "parent_code": "CAT"},
            {"id": 6, "code": "BCN_CITY", "name": "Barcelona City", "level": "municipality", "parent_id": 2, "parent_code": "BCN"},
            {"id": 7, "code": "GIR_CITY", "name": "Girona City", "level": "municipality", "parent_id": 3, "parent_code": "GIR"},
            {"id": 8, "code": "LLE_CITY", "name": "Lleida City", "level": "municipality", "parent_id": 4, "parent_code": "LLE"},
            {"id": 9, "code": "TAR_CITY", "name": "Tarragona City", "level": "municipality", "parent_id": 5, "parent_code": "TAR"},
            {"id": 10, "code": "SITGES", "name": "Sitges", "level": "municipality", "parent_id": 2, "parent_code": "BCN"}
        ]

        result = initialize_dimension_table(
            s3_client, glue_client, bucket_name, database_name,
            'territorial_hierarchy', territorial_hierarchy_data, environment
        )
        tables_created.append('territorial_hierarchy')

        # 3. Service Categories
        service_categories_data = [
            {"id": 1, "code": "HEALTHCARE", "name": "Healthcare", "description": "Medical and health services"},
            {"id": 2, "code": "EDUCATION", "name": "Education", "description": "Educational services and institutions"},
            {"id": 3, "code": "SOCIAL_SERVICES", "name": "Social Services", "description": "Community and social support services"},
            {"id": 4, "code": "RECREATION", "name": "Recreation", "description": "Sports, leisure and recreational services"},
            {"id": 5, "code": "TRANSPORTATION", "name": "Transportation", "description": "Public transport and mobility services"},
            {"id": 6, "code": "CULTURAL", "name": "Cultural", "description": "Museums, theaters and cultural institutions"},
            {"id": 7, "code": "ADMINISTRATIVE", "name": "Administrative", "description": "Government and administrative services"},
            {"id": 8, "code": "EMERGENCY", "name": "Emergency", "description": "Emergency and safety services"}
        ]

        result = initialize_dimension_table(
            s3_client, glue_client, bucket_name, database_name,
            'service_categories', service_categories_data, environment
        )
        tables_created.append('service_categories')

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Default dimension tables created successfully',
                'tables_created': tables_created,
                'table_count': len(tables_created)
            })
        }

    except Exception as e:
        logger.error(f"Error creating default tables: {str(e)}")
        raise


def create_glue_table(glue_client, database_name: str, table_name: str,
                      bucket_name: str, s3_key: str, df: pd.DataFrame):
    """Create Glue table definition."""

    try:
        # Infer schema from DataFrame
        columns = []
        for col_name, dtype in df.dtypes.items():
            if dtype == 'object':
                glue_type = 'string'
            elif dtype == 'int64':
                glue_type = 'bigint'
            elif dtype == 'float64':
                glue_type = 'double'
            elif dtype == 'bool':
                glue_type = 'boolean'
            else:
                glue_type = 'string'

            columns.append({
                'Name': col_name,
                'Type': glue_type
            })

        table_input = {
            'Name': f"dim_{table_name}",
            'Description': f'Dimension table for {table_name}',
            'StorageDescriptor': {
                'Columns': columns,
                'Location': f's3://{bucket_name}/dimension_tables/{table_name}/',
                'InputFormat': 'org.apache.hadoop.mapred.TextInputFormat',
                'OutputFormat': 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat',
                'SerdeInfo': {
                    'SerializationLibrary': 'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe'
                }
            },
            'PartitionKeys': [],
            'TableType': 'EXTERNAL_TABLE',
            'Parameters': {
                'classification': 'parquet',
                'typeOfData': 'file',
                'table_type': 'dimension',
                'record_count': str(len(df))
            }
        }

        glue_client.create_table(
            DatabaseName=database_name,
            TableInput=table_input
        )

        logger.info(f"Created Glue table dim_{table_name}")

    except glue_client.exceptions.AlreadyExistsException:
        logger.info(f"Glue table dim_{table_name} already exists, updating...")
        update_glue_table(glue_client, database_name, table_name, bucket_name, s3_key, df)
    except Exception as e:
        logger.error(f"Error creating Glue table dim_{table_name}: {str(e)}")
        raise


def update_glue_table(glue_client, database_name: str, table_name: str,
                      bucket_name: str, s3_key: str, df: pd.DataFrame):
    """Update existing Glue table definition."""

    try:
        # Get current table
        response = glue_client.get_table(
            DatabaseName=database_name,
            Name=f"dim_{table_name}"
        )

        table_input = response['Table']

        # Remove read-only fields
        for field in ['DatabaseName', 'CreateTime', 'UpdateTime', 'CreatedBy', 'IsRegisteredWithLakeFormation', 'CatalogId']:
            table_input.pop(field, None)

        # Update parameters
        table_input['Parameters']['record_count'] = str(len(df))
        table_input['Parameters']['last_updated'] = datetime.utcnow().isoformat()

        glue_client.update_table(
            DatabaseName=database_name,
            TableInput=table_input
        )

        logger.info(f"Updated Glue table dim_{table_name}")

    except Exception as e:
        logger.error(f"Error updating Glue table dim_{table_name}: {str(e)}")
        raise