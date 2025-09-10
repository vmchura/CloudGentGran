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
    """

    try:
        # Get environment variables
        catalog_bucket = os.environ['CATALOG_BUCKET_NAME']
        environment = os.environ.get('ENVIRONMENT', 'dev')

        # Initialize S3 client
        s3_client = boto3.client('s3')

        # Parse event
        table_name = event.get('table_name')
        table_data = [
            {'service_type_id': 'ADD-001',
             'service_type_description': "Servei de pis amb suport per a persones amb drogodependències (baixa i alta intensitat)"},
            {'service_type_id': 'ADD-002', 'service_type_description': "Servei de prevenció d'addiccions"},
            {'service_type_id': 'ASS-001',
             'service_type_description': "Servei d'assistència personal de suport a la vida autònoma i d'integració social i comunitària, per a persones amb discapacitat física"},
            {'service_type_id': 'ASS-002',
             'service_type_description': "Servei d'assistència personal de suport a la vida autònoma i d'integració social i comunitària, per a persones amb discapacitat sensorial sord-ceguesa"},
            {'service_type_id': 'ASS-003',
             'service_type_description': "Servei d'assistència personal de suport a la vida autònoma id'integració social i comunitària, per a persones amb discapacitat intel·lectual"},
            {'service_type_id': 'ASS-004',
             'service_type_description': "Servei d'assistència personal de suport en l'acompanyament a activitats laborals, ocupacionals i/o formatives, per a persones amb discapacitat física"},
            {'service_type_id': 'ASS-005',
             'service_type_description': "Servei d'assistència personal de suport en l'acompanyament a activitats laborals, ocupacionals i/o formatives, per persones amb discapacitat sensorial sord-ceguesa"},
            {'service_type_id': 'BAS-001', 'service_type_description': "Servei bàsic d'atenció social"},
            {'service_type_id': 'BAS-002',
             'service_type_description': "Servei d'assessorament tècnic d'atenció social"},
            {'service_type_id': 'BAS-003', 'service_type_description': "Servei d'orientació"},
            {'service_type_id': 'BAS-004', 'service_type_description': "Servei de valoració"},
            {'service_type_id': 'BAS-005',
             'service_type_description': "Servei de valoració a la dependència"},
            {'service_type_id': 'BAS-006',
             'service_type_description': "Servei de suport als serveis socials bàsics"},
            {'service_type_id': 'BAS-007',
             'service_type_description': "Servei de suport als serveis socials bàsics ( Distribució d'aliments)"},
            {'service_type_id': 'BAS-008',
             'service_type_description': "Servei de suport als serveis socials bàsics ( Maternoinfantil)"},
            {'service_type_id': 'BAS-009',
             'service_type_description': "Servei de suport social als serveis socials especialitzats"},
            {'service_type_id': 'DAY-001',
             'service_type_description': "Servei de centre de dia per a gent gran de caràcter temporal o permanent"},
            {'service_type_id': 'DAY-002',
             'service_type_description': "Servei de centre per a l'autonomia personal"},
            {'service_type_id': 'DAY-003',
             'service_type_description': "Espai alternatiu d'atenció diürna temporal"},
            {'service_type_id': 'DAY-011',
             'service_type_description': "Servei de centre de dia d'atenció especialitzada temporal o permanent per a persones amb discapacitat física"},
            {'service_type_id': 'DAY-012',
             'service_type_description': "Servei de centre de dia d'atenció especialitzada temporal o permanent per a persones amb discapacitat intel·lectual"},
            {'service_type_id': 'DAY-013',
             'service_type_description': "Servei de centre de dia de teràpia ocupacional (STO) per a  persones amb discapacitat física"},
            {'service_type_id': 'DAY-014',
             'service_type_description': "Servei de centre de dia de teràpia ocupacional per a persones amb discapacitat intel·lectual (STO)"},
            {'service_type_id': 'DAY-015',
             'service_type_description': "Servei de centre de dia ocupacional d'inserció (SOI) per a  persones amb discapacitat física"},
            {'service_type_id': 'DAY-016',
             'service_type_description': "Servei de centre de dia ocupacional d'inserció per a persones amb discapacitat intel·lectual (SOI)"},
            {'service_type_id': 'DAY-021',
             'service_type_description': "Servei de centre de dia per a persones amb addiccions"},
            {'service_type_id': 'DAY-022',
             'service_type_description': "Servei de club social (mòdul A / mòdul B)"},
            {'service_type_id': 'EXP-001', 'service_type_description': "Servei experimental"},
            {'service_type_id': 'EXP-002',
             'service_type_description': "Servei experimental (Servei de temps lliure per a discapacitats físics)"},
            {'service_type_id': 'EXP-003',
             'service_type_description': "Servei experimental (Tutela discapacitats físics-diversa)"},
            {'service_type_id': 'FAM-001',
             'service_type_description': "Servei d'atenció a les famílies (amb problemàtica social de risc d'exclusió social)"},
            {'service_type_id': 'FAM-002', 'service_type_description': "Servei d'atenció precoç"},
            {'service_type_id': 'FAM-003',
             'service_type_description': "Servei de suport a l'adopció internacional"},
            {'service_type_id': 'HIV-001',
             'service_type_description': "Servei de prevenció per a persones afectades pel virus VIH/SIDA"},
            {'service_type_id': 'HIV-002',
             'service_type_description': "Servei temporal de llar amb suport per a persones afectades pel virus VIH/SIDA (baixa/alta intensitat)"},
            {'service_type_id': 'HIV-003',
             'service_type_description': "Servei temporal de llar residència per a persones afectades pel virus  VIH/SIDA"},
            {'service_type_id': 'HOM-001', 'service_type_description': "Servei d'ajuda a domicili"},
            {'service_type_id': 'HOM-002',
             'service_type_description': "Servei de suport a l'autonomia a la pròpia llar per a persones amb discapacitat física"},
            {'service_type_id': 'HOM-003',
             'service_type_description': "Servei de suport a l'autonomia a la pròpia llar per a persones amb discapacitat intel·lectual"},
            {'service_type_id': 'HOM-004',
             'service_type_description': "Servei de suport a l'autonomia a la pròpia llar per a persones amb problemàtica social derivada de malaltia mental"},
            {'service_type_id': 'HOM-005',
             'service_type_description': "Servei de suport als familiars cuidadors/es i altres cuidadors/es no professionals"},
            {'service_type_id': 'PRE-001',
             'service_type_description': "Servei de prevenció de les situacions de dependència"},
            {'service_type_id': 'RES-001',
             'service_type_description': "Servei d' habitatge tutelat per a gent gran de caràcter temporal o permanent"},
            {'service_type_id': 'RES-002',
             'service_type_description': "Servei de llar residència per a gent gran de caràcter temporal o permanent"},
            {'service_type_id': 'RES-003',
             'service_type_description': "Servei de residència assistida per a gent gran de caràcter temporal o permanent"},
            {'service_type_id': 'RES-011',
             'service_type_description': "Servei de centre residencial temporal o permanent per a persones amb discapacitat física"},
            {'service_type_id': 'RES-012',
             'service_type_description': "Servei de centre residencial temporal o permanent per a persones amb discapacitat intel·lectual"},
            {'service_type_id': 'RES-013',
             'service_type_description': "Servei de llar amb suport per a persones amb discapacitat física"},
            {'service_type_id': 'RES-014',
             'service_type_description': "Servei de llar amb suport per a persones amb discapacitat intel·lectual"},
            {'service_type_id': 'RES-015',
             'service_type_description': "Servei de llar residència temporal o permanent per a persones amb discapacitat física"},
            {'service_type_id': 'RES-016',
             'service_type_description': "Servei de llar residència temporal o permanent per a persones amb discapacitat intel·lectual"},
            {'service_type_id': 'RES-021',
             'service_type_description': "Servei de llar amb suport temporal o permanent per a persones amb problemàtica social derivada de malaltia mental"},
            {'service_type_id': 'RES-022',
             'service_type_description': "Servei de llar residència temporal o permanent per a persones amb problemàtica social derivada de malaltia mental"},
            {'service_type_id': 'RES-023',
             'service_type_description': "Servei de residència temporal per a persones adultes en situació d'exclusió social"},
            {'service_type_id': 'RES-024',
             'service_type_description': "Servei d'acolliment residencial d'urgència"},
            {'service_type_id': 'RES-025', 'service_type_description': "Casal per a altres col·lectius"},
            {'service_type_id': 'RUR-001',
             'service_type_description': "Servei d'atenció integral a les persones grans en l'àmbit rural"},
            {'service_type_id': 'SUP-001',
             'service_type_description': "Servei d'intèrpret per a persones sordes"},
            {'service_type_id': 'SUP-002',
             'service_type_description': "Servei de les tecnologies de suport i cura"},
            {'service_type_id': 'SUP-003', 'service_type_description': "Servei de transport adaptat"},
            {'service_type_id': 'SUP-004', 'service_type_description': "Servei de menjador social"},
            {'service_type_id': 'SUP-005',
             'service_type_description': "Servei de temps lliure per a persones amb discapacitat intel·lectual"},
            {'service_type_id': 'TUT-001', 'service_type_description': "Servei de tutela per a gent gran"},
            {'service_type_id': 'TUT-002',
             'service_type_description': "Servei de tutela per a persones amb discapacitat intel·lectual"},
            {'service_type_id': 'TUT-003',
             'service_type_description': "Servei de tutela per a persones amb malaltia mental"},
            {'service_type_id': 'WOR-001', 'service_type_description': "Servei prelaboral"}]

        if not table_name:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'table_name is required'})
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
                        data: List[Dict]) -> Dict:
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

        # Create S3 key with timestamp for uniqueness
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        s3_key = f"{table_name}/{timestamp}.parquet"

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
