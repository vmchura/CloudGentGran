import pytest
from unittest.mock import Mock, patch
from api_extractor import (
    lambda_handler
)
def my_side_effect(bucket_name: str, json_data: bytes, semantic_identifier: str) -> str:
    print(bucket_name)
    print(json_data is None)
    print(semantic_identifier)
    return "landing/semantic_identifier"


@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv('BUCKET_NAME', 'test-bucket')
    monkeypatch.setenv('SEMANTIC_IDENTIFIER', 'test-comarca')
    monkeypatch.delenv('AWS_ENDPOINT_URL', raising=False)

def test_lambda_handler_success(mock_env):
    with patch('api_extractor.upload_to_s3', side_effect=my_side_effect):
        response = lambda_handler({}, None)
        print(response)
    assert response['statusCode'] == 200