import json
import boto3
import pandas as pd
import os
from typing import Dict, List, Any
from datetime import datetime
import logging
from io import BytesIO

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Simplified Lambda function to create raw parquet files from input data.
    
    This function takes input data and creates parquet files directly in S3
    without any AWS Glue integration.
    
    Event structure:
    {
        "table_name": "my_dimension_table",
        "data": [
            {"id": 1, "name": "Example", "category": "test"},
            {"id": 2, "name": "Another", "category": "test"}
        ]
    }
    """

    try:
        # Get environment variables
        catalog_bucket = os.environ['CATALOG_BUCKET_NAME']
        environment = os.environ.get('ENVIRONMENT', 'dev')

        # Initialize S3 client
        s3_client = boto3.client('s3')

        # Parse event
        table_name = event.get('table_name')
        table_data = event.get('data', [])

        if not table_name:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'table_name is required'})
            }

        if not table_data:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'data is required and cannot be empty'})
            }

        logger.info(f"Creating parquet file for table: {table_name} with {len(table_data)} records")

        # Create parquet file
        response = create_parquet_file(s3_client, catalog_bucket, table_name, table_data, environment)

        logger.info(f"Successfully created parquet file for table: {table_name}")
        return response

    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def create_parquet_file(s3_client, bucket_name: str, table_name: str,
                        data: List[Dict], environment: str) -> Dict:
    """
    Create a parquet file from the input data and upload it to S3.
    """

    try:
        # Create DataFrame from input data
        df = pd.DataFrame(data)

        if df.empty:
            raise ValueError(f"No data provided for table {table_name}")

        # Add metadata columns
        current_time = datetime.utcnow().isoformat()
        df['created_at'] = current_time
        df['environment'] = environment

        # Create S3 key with timestamp for uniqueness
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        s3_key = f"raw_parquet/{table_name}/{timestamp}.parquet"

        # Convert DataFrame to parquet in memory
        parquet_buffer = BytesIO()
        df.to_parquet(parquet_buffer, engine='fastparquet', index=False)
        parquet_buffer.seek(0)

        # Upload to S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=parquet_buffer.getvalue(),
            ContentType='application/octet-stream',
            Metadata={
                'table_name': table_name,
                'environment': environment,
                'record_count': str(len(df)),
                'created_at': current_time,
                'original_columns': json.dumps(list(data[0].keys()) if data else [])
            }
        )

        s3_location = f's3://{bucket_name}/{s3_key}'

        logger.info(f"Created parquet file for {table_name} with {len(df)} records at {s3_location}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Parquet file created successfully for table {table_name}',
                'table_name': table_name,
                'record_count': len(df),
                's3_location': s3_location,
                's3_key': s3_key,
                'columns': list(df.columns),
                'created_at': current_time
            })
        }

    except Exception as e:
        logger.error(f"Error creating parquet file for {table_name}: {str(e)}")
        raise