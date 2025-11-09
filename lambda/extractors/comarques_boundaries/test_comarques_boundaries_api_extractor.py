import pytest
from unittest.mock import Mock, patch
from io import BytesIO
from zipfile import ZipFile
from api_extractor import (
    lambda_handler,
    extract_epsg_from_prj,
    transform_coordinates,
    shape_parts_to_rings,
    shape_type_to_geojson,
    upload_to_s3,
    create_response,
    get_s3_client
)


@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv('BUCKET_NAME', 'test-bucket')
    monkeypatch.setenv('SEMANTIC_IDENTIFIER', 'test-comarca')
    monkeypatch.delenv('AWS_ENDPOINT_URL', raising=False)


def test_get_s3_client_default():
    with patch.dict('os.environ', {}, clear=True):
        with patch('boto3.client') as mock_boto:
            get_s3_client()
            mock_boto.assert_called_once_with('s3')


def test_get_s3_client_custom_endpoint():
    with patch.dict('os.environ', {'AWS_ENDPOINT_URL': 'http://localhost:4566'}):
        with patch('boto3.client') as mock_boto:
            get_s3_client()
            mock_boto.assert_called_once_with('s3', endpoint_url='http://localhost:4566')


def test_extract_epsg_from_prj_etrs89():
    prj_content = 'PROJCS["ETRS89 / UTM zone 31N"]'
    assert extract_epsg_from_prj(prj_content) == 25831


def test_extract_epsg_from_prj_epsg_25831():
    prj_content = 'AUTHORITY["EPSG",25831]]'
    assert extract_epsg_from_prj(prj_content) == 25831


def test_extract_epsg_from_prj_default():
    prj_content = 'PROJCS["Unknown"]'
    assert extract_epsg_from_prj(prj_content) == 25831


def test_shape_type_to_geojson():
    assert shape_type_to_geojson(1) == "Point"
    assert shape_type_to_geojson(11) == "Point"
    assert shape_type_to_geojson(21) == "Point"
    assert shape_type_to_geojson(3) == "LineString"
    assert shape_type_to_geojson(13) == "LineString"
    assert shape_type_to_geojson(23) == "LineString"
    assert shape_type_to_geojson(5) == "Polygon"
    assert shape_type_to_geojson(15) == "Polygon"
    assert shape_type_to_geojson(25) == "Polygon"
    assert shape_type_to_geojson(8) == "MultiPoint"
    assert shape_type_to_geojson(999) == "Polygon"


def test_shape_parts_to_rings():
    mock_shape = Mock()
    mock_shape.parts = [0, 5]
    mock_shape.points = [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6)]

    rings = shape_parts_to_rings(mock_shape)

    assert len(rings) == 2
    assert rings[0] == [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4)]
    assert rings[1] == [(5, 5), (6, 6)]


def test_transform_coordinates_polygon():
    mock_shape = Mock()
    mock_shape.shapeType = 5
    mock_shape.parts = [0]
    mock_shape.points = [(420000.0, 4650000.0), (420100.0, 4650000.0), (420000.0, 4650100.0)]

    mock_transformer = Mock()
    mock_transformer.transform = Mock(side_effect=lambda x, y: (x / 100000, y / 100000))

    coords = transform_coordinates(mock_shape, mock_transformer)

    assert len(coords) == 1
    assert len(coords[0]) == 1
    assert coords[0][0][0] == (4.2, 46.5)


def test_transform_coordinates_linestring():
    mock_shape = Mock()
    mock_shape.shapeType = 3
    mock_shape.parts = [0]
    mock_shape.points = [(420000.0, 4650000.0), (420100.0, 4650000.0)]

    mock_transformer = Mock()
    mock_transformer.transform = Mock(side_effect=lambda x, y: (x / 100000, y / 100000))

    coords = transform_coordinates(mock_shape, mock_transformer)

    assert len(coords) == 1
    assert coords[0][0] == (4.2, 46.5)


def test_transform_coordinates_point():
    mock_shape = Mock()
    mock_shape.shapeType = 1
    mock_shape.points = [(420000.0, 4650000.0)]

    mock_transformer = Mock()
    mock_transformer.transform = Mock(return_value=(4.2, 46.5))

    coords = transform_coordinates(mock_shape, mock_transformer)

    assert coords == [4.2, 46.5]


def test_create_response_success():
    response = create_response(True, "Test success", {'key': 'value'})

    assert response['statusCode'] == 200
    assert response['success'] is True
    assert response['message'] == "Test success"
    assert response['data']['key'] == 'value'
    assert response['extractor'] == 'comarques-boundaries-extractor'
    assert 'timestamp' in response


def test_create_response_failure():
    response = create_response(False, "Test error")

    assert response['statusCode'] == 500
    assert response['success'] is False
    assert response['message'] == "Test error"
    assert 'data' not in response


@patch('api_extractor.boto3.client')
def test_upload_to_s3_success(mock_boto_client):
    mock_s3 = Mock()
    mock_boto_client.return_value = mock_s3

    test_data = b'{"test": "data"}'

    s3_key = upload_to_s3('test-bucket', test_data, 'test-semantic')

    assert 'landing/test-semantic/' in s3_key
    assert s3_key.endswith('.json')
    mock_s3.put_object.assert_called_once()

    call_args = mock_s3.put_object.call_args
    assert call_args[1]['Bucket'] == 'test-bucket'
    assert call_args[1]['Body'] == test_data
    assert call_args[1]['ContentType'] == 'application/json'


@patch('api_extractor.boto3.client')
def test_upload_to_s3_failure(mock_boto_client):
    mock_s3 = Mock()
    mock_s3.put_object.side_effect = Exception("S3 error")
    mock_boto_client.return_value = mock_s3

    with pytest.raises(Exception, match="S3 error"):
        upload_to_s3('test-bucket', b'data', 'test-semantic')


@patch('api_extractor.Transformer')
@patch('api_extractor.shapefile.Reader')
@patch('api_extractor.boto3.client')
@patch('api_extractor.urlopen')
def test_lambda_handler_success(mock_urlopen, mock_boto_client, mock_shapefile, mock_transformer_cls, mock_env):
    mock_zip = BytesIO()
    with ZipFile(mock_zip, 'w') as zf:
        zf.writestr('comarques-1000000.shp', b'shp')
        zf.writestr('comarques-1000000.shx', b'shx')
        zf.writestr('comarques-1000000.dbf', b'dbf')
        zf.writestr('comarques-1000000.prj', b'PROJCS["ETRS89"]')
    mock_zip.seek(0)

    mock_response = Mock()
    mock_response.read.return_value = mock_zip.getvalue()
    mock_urlopen.return_value = mock_response

    mock_shape_record = Mock()
    mock_shape_record.shape = Mock(
        shapeType=5,
        points=[(420000.0, 4650000.0), (420100.0, 4650000.0), (420000.0, 4650100.0)],
        parts=[0]
    )
    mock_shape_record.record = ['Comarca Test', 123]

    mock_sf = Mock()
    mock_sf.shapes.return_value = [mock_shape_record.shape]
    mock_sf.fields = [['DeletionFlag', 'C', 1, 0], ['NAME', 'C', 50, 0], ['CODE', 'N', 10, 0]]
    mock_sf.shapeRecords.return_value = [mock_shape_record]

    mock_shapefile.return_value = mock_sf

    mock_transformer = Mock()
    mock_transformer.transform = Mock(side_effect=lambda x, y: (x / 100000, y / 100000))
    mock_transformer_cls.from_crs.return_value = mock_transformer

    mock_s3 = Mock()
    mock_boto_client.return_value = mock_s3

    response = lambda_handler({}, None)

    assert response['statusCode'] == 200
    assert response['success'] is True
    assert 'Successfully extracted' in response['message']
    assert response['data']['bucket'] == 'test-bucket'
    mock_s3.put_object.assert_called_once()


@patch('api_extractor.urlopen')
def test_lambda_handler_download_failure(mock_urlopen, mock_env):
    mock_urlopen.side_effect = Exception("Download failed")

    response = lambda_handler({}, None)

    assert response['statusCode'] == 500
    assert response['success'] is False
    assert 'Download failed' in response['message']


@patch('api_extractor.urlopen')
def test_lambda_handler_missing_shapefile_components(mock_urlopen, mock_env):
    mock_zip = BytesIO()
    with ZipFile(mock_zip, 'w') as zf:
        zf.writestr('comarques-1000000.shp', b'shp')
    mock_zip.seek(0)

    mock_response = Mock()
    mock_response.read.return_value = mock_zip.getvalue()
    mock_urlopen.return_value = mock_response

    response = lambda_handler({}, None)

    assert response['statusCode'] == 500
    assert response['success'] is False
    assert 'Missing required shapefile components' in response['message']
