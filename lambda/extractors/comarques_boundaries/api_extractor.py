import json
import boto3
import logging
from datetime import datetime
from typing import Dict, Any
import os
from io import BytesIO
from zipfile import ZipFile
from urllib.request import urlopen
import shapefile
from pyproj import Transformer

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_s3_client():
    endpoint_url = os.environ.get('AWS_ENDPOINT_URL')
    if endpoint_url:
        logger.info(f"Using S3 endpoint: {endpoint_url}")
        return boto3.client('s3', endpoint_url=endpoint_url)
    else:
        logger.info("Using default S3 endpoint")
        return boto3.client('s3')

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    try:
        logger.info(f"Starting comarques boundaries extraction at {datetime.utcnow()}")

        bucket_name = os.environ['BUCKET_NAME']
        semantic_identifier = os.environ['SEMANTIC_IDENTIFIER']

        catalunya_zip_url = 'https://datacloud.icgc.cat/datacloud/divisions-administratives/shp/divisions-administratives-v2r1-20250730.zip'

        file_response_by_request = urlopen(catalunya_zip_url)
        zip_file_memory = ZipFile(BytesIO(file_response_by_request.read()))

        files_shape_selected = [file_name for file_name in zip_file_memory.namelist() if 'comarques-1000000' in file_name]

        shp_file = next((f for f in files_shape_selected if f.endswith('.shp')), None)
        shx_file = next((f for f in files_shape_selected if f.endswith('.shx')), None)
        dbf_file = next((f for f in files_shape_selected if f.endswith('.dbf')), None)
        prj_file = next((f for f in files_shape_selected if f.endswith('.prj')), None)

        if not all([shp_file, shx_file, dbf_file]):
            raise Exception("Missing required shapefile components")

        shp_bytes = zip_file_memory.read(shp_file)
        shx_bytes = zip_file_memory.read(shx_file)
        dbf_bytes = zip_file_memory.read(dbf_file)

        sf = shapefile.Reader(shp=BytesIO(shp_bytes), shx=BytesIO(shx_bytes), dbf=BytesIO(dbf_bytes))

        logger.info(f"Loaded {len(sf.shapes())} geometries")

        prj_content = zip_file_memory.read(prj_file).decode('utf-8') if prj_file else None
        source_epsg = extract_epsg_from_prj(prj_content) if prj_content else 25831

        logger.info(f"Source CRS detected: EPSG:{source_epsg}")

        transformer = Transformer.from_crs(f"EPSG:{source_epsg}", "EPSG:4326", always_xy=True)

        geojson = {
            "type": "FeatureCollection",
            "features": []
        }

        fields = [field[0] for field in sf.fields[1:]]

        for i, shape_record in enumerate(sf.shapeRecords()):
            shape = shape_record.shape
            record = shape_record.record

            transformed_coords = transform_coordinates(shape, transformer)
            print(dict(zip(fields, record)))
            feature = {
                "id": f"{i}",
                "type": "Feature",
                "properties": dict(zip(fields, record)),
                "geometry": {
                    "type": shape_type_to_geojson(shape.shapeType),
                    "coordinates": transformed_coords
                }
            }
            geojson["features"].append(feature)

        logger.info(f"Converted {len(geojson['features'])} features to GeoJSON CRS 4326")
        with open('comarca_transformed_shape.json', 'w') as f:
            json.dump(geojson, f)

        geojson_str = json.dumps(geojson, ensure_ascii=False)
        geojson_bytes = geojson_str.encode('utf-8')

        s3_key = upload_to_s3(bucket_name, geojson_bytes, semantic_identifier)

        logger.info("Successfully completed extraction")

        return create_response(True, "Successfully extracted comarques boundaries",
                               {
                                   'bucket': bucket_name,
                                   'semantic_identifier': semantic_identifier,
                                   's3_key': s3_key,
                                   'extraction_completed_at': datetime.utcnow().isoformat()
                               })

    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return create_response(False, f"Error: {str(e)}")

def extract_epsg_from_prj(prj_content: str) -> int:
    if 'EPSG",25831' in prj_content or 'ETRS89' in prj_content:
        return 25831
    return 25831

def transform_coordinates(shape, transformer):
    if shape.shapeType in [5, 15, 25]:
        return [
            [
                [transformer.transform(x, y) for x, y in part]
                for part in shape_parts_to_rings(shape)
            ]
        ]
    elif shape.shapeType in [3, 13, 23]:
        return [
            [transformer.transform(x, y) for x, y in part]
            for part in shape_parts_to_rings(shape)
        ]
    elif shape.shapeType in [1, 11, 21]:
        return list(transformer.transform(shape.points[0][0], shape.points[0][1]))
    return []

def shape_parts_to_rings(shape):
    parts = list(shape.parts) + [len(shape.points)]
    return [shape.points[parts[i]:parts[i+1]] for i in range(len(parts)-1)]

def shape_type_to_geojson(shape_type: int) -> str:
    mapping = {
        1: "Point", 11: "Point", 21: "Point",
        3: "LineString", 13: "LineString", 23: "LineString",
        5: "Polygon", 15: "Polygon", 25: "Polygon",
        8: "MultiPoint", 18: "MultiPoint", 28: "MultiPoint"
    }
    return mapping.get(shape_type, "Polygon")

def upload_to_s3(bucket_name: str, json_data: bytes, semantic_identifier: str) -> str:
    try:
        s3_client = get_s3_client()

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        s3_key = f"landing/{semantic_identifier}/{timestamp}.json"

        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json_data,
            ContentType='application/json',
            Metadata={
                'extractor': 'comarques-boundaries-extractor',
                'semantic_identifier': semantic_identifier,
                'extraction_timestamp': datetime.utcnow().isoformat()
            }
        )

        logger.info(f"Successfully uploaded to s3://{bucket_name}/{s3_key}")
        return s3_key

    except Exception as e:
        logger.error(f"Failed to upload to S3: {str(e)}")
        raise

def create_response(success: bool, message: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
    response = {
        'statusCode': 200 if success else 500,
        'success': success,
        'message': message,
        'timestamp': datetime.utcnow().isoformat(),
        'extractor': 'comarques-boundaries-extractor'
    }

    if data:
        response['data'] = data

    return response