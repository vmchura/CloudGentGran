import json
import boto3
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
import os
from io import BytesIO
from zipfile import ZipFile
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
import shapefile
from pyproj import Transformer
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class ComarquesExtractorError(Exception):
    """Base exception for comarques boundaries extractor errors"""

    pass


class ConfigurationError(ComarquesExtractorError):
    """Raised when there's a configuration error"""

    pass


class DownloadError(ComarquesExtractorError):
    """Raised when downloading data fails"""

    pass


class DataProcessingError(ComarquesExtractorError):
    """Raised when data processing fails"""

    pass


class S3OperationError(ComarquesExtractorError):
    """Raised when S3 operations fail"""

    pass


def get_s3_client():
    """Get S3 client with optional endpoint URL for LocalStack"""
    endpoint_url = os.environ.get("AWS_ENDPOINT_URL")
    if endpoint_url:
        logger.info(f"Using S3 endpoint: {endpoint_url}")
        return boto3.client("s3", endpoint_url=endpoint_url)
    else:
        logger.info("Using default S3 endpoint")
        return boto3.client("s3")


def validate_environment() -> tuple[str, str]:
    """Validate required environment variables"""
    bucket_name = os.environ.get("BUCKET_NAME")
    semantic_identifier = os.environ.get("SEMANTIC_IDENTIFIER")

    missing_vars = []
    if not bucket_name:
        missing_vars.append("BUCKET_NAME")
    if not semantic_identifier:
        missing_vars.append("SEMANTIC_IDENTIFIER")

    if missing_vars:
        raise ConfigurationError(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )

    return bucket_name, semantic_identifier


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main Lambda handler function"""
    try:
        logger.info(
            f"Starting comarques boundaries extraction at {datetime.now().isoformat()}"
        )

        # Validate environment variables
        bucket_name, semantic_identifier = validate_environment()

        catalunya_zip_url = "https://datacloud.icgc.cat/datacloud/divisions-administratives/shp/divisions-administratives-v2r1-20250730.zip"

        # Download zip file
        try:
            file_response_by_request = urlopen(catalunya_zip_url, timeout=60)
            zip_file_memory = ZipFile(BytesIO(file_response_by_request.read()))
        except HTTPError as e:
            raise DownloadError(f"HTTP {e.code} error downloading data: {e.reason}")
        except URLError as e:
            raise DownloadError(f"URL error downloading data: {e.reason}")
        except TimeoutError:
            raise DownloadError("Timeout error downloading data")
        except Exception as e:
            raise DownloadError(f"Error downloading or parsing zip file: {str(e)}")

        list_s3_keys: List[str] = []

        def process_level(level: str, properties_parser: Callable[[Dict], Dict]) -> str:
            """Process a single level (comarques or municipis)"""
            try:
                files_shape_selected = [
                    file_name
                    for file_name in zip_file_memory.namelist()
                    if level in file_name
                ]

                shp_file = next(
                    (f for f in files_shape_selected if f.endswith(".shp")), None
                )
                shx_file = next(
                    (f for f in files_shape_selected if f.endswith(".shx")), None
                )
                dbf_file = next(
                    (f for f in files_shape_selected if f.endswith(".dbf")), None
                )
                prj_file = next(
                    (f for f in files_shape_selected if f.endswith(".prj")), None
                )

                if not all([shp_file, shx_file, dbf_file]):
                    raise DataProcessingError(
                        f"Missing required shapefile components for level {level}"
                    )

                try:
                    shp_bytes = zip_file_memory.read(shp_file)
                    shx_bytes = zip_file_memory.read(shx_file)
                    dbf_bytes = zip_file_memory.read(dbf_file)
                except Exception as e:
                    raise DataProcessingError(
                        f"Error reading shapefile components: {str(e)}"
                    )

                try:
                    sf = shapefile.Reader(
                        shp=BytesIO(shp_bytes),
                        shx=BytesIO(shx_bytes),
                        dbf=BytesIO(dbf_bytes),
                    )
                except Exception as e:
                    raise DataProcessingError(f"Error parsing shapefile: {str(e)}")

                logger.info(f"Loaded {len(sf.shapes())} geometries")

                prj_content = (
                    zip_file_memory.read(prj_file).decode("utf-8") if prj_file else None
                )
                source_epsg = (
                    extract_epsg_from_prj(prj_content) if prj_content else 25831
                )

                logger.info(f"Source CRS detected: EPSG:{source_epsg}")

                try:
                    transformer = Transformer.from_crs(
                        f"EPSG:{source_epsg}", "EPSG:4326", always_xy=True
                    )
                except Exception as e:
                    raise DataProcessingError(
                        f"Error creating coordinate transformer: {str(e)}"
                    )

                geojson = {"type": "FeatureCollection", "features": []}

                fields = [field[0] for field in sf.fields[1:]]

                for i, shape_record in enumerate(sf.shapeRecords()):
                    try:
                        shape = shape_record.shape
                        record = shape_record.record

                        transformed_coords = transform_coordinates(shape, transformer)

                        # Parse properties
                        try:
                            properties = properties_parser(dict(zip(fields, record)))
                        except KeyError as e:
                            raise DataProcessingError(
                                f"Missing required property in record {i}: {str(e)}"
                            )

                        feature = {
                            "id": f"{i}",
                            "type": "Feature",
                            "properties": properties,
                            "geometry": {
                                "type": shape_type_to_geojson(shape.shapeType),
                                "coordinates": transformed_coords,
                            },
                        }
                        geojson["features"].append(feature)
                    except DataProcessingError:
                        raise
                    except Exception as e:
                        raise DataProcessingError(
                            f"Error processing shape record {i}: {str(e)}"
                        )

                logger.info(
                    f"Converted {len(geojson['features'])} features to GeoJSON CRS 4326"
                )

                try:
                    geojson_str = json.dumps(geojson, ensure_ascii=False)
                    geojson_bytes = geojson_str.encode("utf-8")
                except Exception as e:
                    raise DataProcessingError(f"Error encoding GeoJSON: {str(e)}")

                return upload_to_s3(
                    bucket_name, geojson_bytes, semantic_identifier, level
                )
            except DataProcessingError:
                raise
            except Exception as e:
                raise DataProcessingError(f"Error processing level {level}: {str(e)}")

        for single_level in ["comarques-1000000", "municipis-1000000"]:
            if "comarques" in single_level:
                parser_parameters = lambda current_properties: {
                    "comarca_id": current_properties["CODICOMAR"]
                }
            else:
                parser_parameters = lambda current_properties: {
                    "municipal_id": current_properties["CODIMUNI"]
                }

            s3_key = process_level(single_level, parser_parameters)
            list_s3_keys.append(s3_key)

        logger.info("Successfully completed extraction")

        return create_response(
            True,
            "Successfully extracted comarques boundaries",
            {
                "bucket": bucket_name,
                "semantic_identifier": semantic_identifier,
                "list_s3_keys": list_s3_keys,
                "extraction_completed_at": datetime.now().isoformat(),
            },
        )

    except ConfigurationError as e:
        logger.error(f"Configuration error: {str(e)}")
        return create_response(False, str(e), {"error_type": "ConfigurationError"})
    except DownloadError as e:
        logger.error(f"Download error: {str(e)}")
        return create_response(False, str(e), {"error_type": "DownloadError"})
    except DataProcessingError as e:
        logger.error(f"Data processing error: {str(e)}")
        return create_response(False, str(e), {"error_type": "DataProcessingError"})
    except S3OperationError as e:
        logger.error(f"S3 operation error: {str(e)}")
        return create_response(False, str(e), {"error_type": "S3OperationError"})
    except (ClientError, NoCredentialsError, EndpointConnectionError) as e:
        logger.error(f"AWS service error: {str(e)}")
        return create_response(
            False,
            "AWS service error",
            {
                "error_type": type(e).__name__,
                "message": "Failed to connect to AWS services",
            },
        )
    except ComarquesExtractorError as e:
        logger.error(f"Extractor error: {str(e)}")
        return create_response(False, str(e), {"error_type": "ComarquesExtractorError"})
    except Exception as e:
        logger.error(f"Unexpected error in lambda_handler: {str(e)}")
        return create_response(
            False, "An unexpected error occurred", {"error_type": type(e).__name__}
        )


def extract_epsg_from_prj(prj_content: str) -> int:
    """Extract EPSG code from PRJ file content"""
    if 'EPSG",25831' in prj_content or "ETRS89" in prj_content:
        return 25831
    return 25831


def transform_coordinates(shape, transformer):
    """Transform shape coordinates to target CRS"""
    try:
        if shape.shapeType in [5, 15, 25]:
            return [
                [transformer.transform(x, y) for x, y in part]
                for part in shape_parts_to_rings(shape)
            ]
        elif shape.shapeType in [3, 13, 23]:
            return [
                [transformer.transform(x, y) for x, y in part]
                for part in shape_parts_to_rings(shape)
            ]
        elif shape.shapeType in [1, 11, 21]:
            return list(transformer.transform(shape.points[0][0], shape.points[0][1]))
        return []
    except Exception as e:
        raise DataProcessingError(f"Error transforming coordinates: {str(e)}")


def shape_parts_to_rings(shape):
    """Convert shape parts to rings"""
    parts = list(shape.parts) + [len(shape.points)]
    return [shape.points[parts[i] : parts[i + 1]] for i in range(len(parts) - 1)]


def shape_type_to_geojson(shape_type: int) -> str:
    """Map shapefile type to GeoJSON type"""
    mapping = {
        1: "Point",
        11: "Point",
        21: "Point",
        3: "LineString",
        13: "LineString",
        23: "LineString",
        5: "Polygon",
        15: "Polygon",
        25: "Polygon",
        8: "MultiPoint",
        18: "MultiPoint",
        28: "MultiPoint",
    }
    return mapping.get(shape_type, "Polygon")


def upload_to_s3(
    bucket_name: str, json_data: bytes, semantic_identifier: str, level: str
) -> str:
    """Upload GeoJSON data to S3"""
    try:
        s3_client = get_s3_client()

        s3_key = f"landing/{semantic_identifier}/{level}.json"

        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json_data,
            ContentType="application/json",
            Metadata={
                "extractor": "comarques-boundaries-extractor",
                "semantic_identifier": semantic_identifier,
                "extraction_timestamp": datetime.now().isoformat(),
            },
        )

        logger.info(f"Successfully uploaded to s3://{bucket_name}/{s3_key}")
        return s3_key

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        logger.error(f"AWS S3 error ({error_code}): {error_message}")
        raise S3OperationError(f"S3 upload failed: {error_message}")
    except Exception as e:
        logger.error(f"Failed to upload to S3: {str(e)}")
        raise S3OperationError(f"S3 upload failed: {str(e)}")


def create_response(
    success: bool, message: str, data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create standardized Lambda response"""
    response: Dict[str, Any] = {
        "statusCode": 200 if success else 500,
        "success": success,
        "message": message,
        "timestamp": datetime.now().isoformat(),
        "extractor": "comarques-boundaries-extractor",
    }

    if data:
        response["data"] = data

    return response
