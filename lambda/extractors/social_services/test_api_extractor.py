import unittest
from unittest.mock import patch, MagicMock
import json
import os
from api_extractor import (
    lambda_handler,
    upload_to_s3,
    create_response,
    get_s3_client,
)


class TestSocialServicesApiExtractor(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "BUCKET_NAME": "test-bucket",
            "DATASET_IDENTIFIER": "test-dataset",
            "SEMANTIC_IDENTIFIER": "test-semantic",
        },
    )
    @patch("api_extractor.get_s3_client")
    @patch("api_extractor.urllib.request.urlopen")
    def test_lambda_handler_success(self, mock_urlopen, mock_s3_client):
        """Test successful lambda execution"""
        mock_s3 = MagicMock()
        mock_s3_client.return_value = mock_s3

        # Mock the API responses - first with data, then empty to signal end
        mock_responses = [
            [
                {"codi": "001", "nom": "Entity1"},
                {"codi": "002", "nom": "Entity2"},
            ],  # First iteration with data
            [],  # Empty response to signal end of data
        ]

        mock_contexts = []
        for resp in mock_responses:
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps(resp).encode("utf-8")
            mock_cm = MagicMock()
            mock_cm.__enter__.return_value = mock_response
            mock_cm.__exit__.return_value = False
            mock_contexts.append(mock_cm)

        mock_urlopen.side_effect = mock_contexts

        result = lambda_handler({}, None)

        self.assertEqual(result["statusCode"], 200)
        self.assertTrue(result["success"])
        self.assertIn("data", result)
        self.assertEqual(result["data"]["total_records"], 2)
        self.assertEqual(result["data"]["file_count"], 1)

    @patch.dict(
        os.environ,
        {
            "BUCKET_NAME": "test-bucket",
            "DATASET_IDENTIFIER": "test-dataset",
            "SEMANTIC_IDENTIFIER": "test-semantic",
        },
    )
    @patch("api_extractor.urllib.request.urlopen")
    def test_lambda_handler_no_data(self, mock_urlopen):
        """Test lambda handler when no data is available"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps([]).encode("utf-8")
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = mock_response
        mock_cm.__exit__.return_value = False
        mock_urlopen.return_value = mock_cm

        result = lambda_handler({}, None)

        self.assertEqual(result["statusCode"], 500)
        self.assertFalse(result["success"])
        self.assertIn("No data extracted", result["message"])

    @patch.dict(
        os.environ,
        {
            "BUCKET_NAME": "test-bucket",
            "DATASET_IDENTIFIER": "test-dataset",
            "SEMANTIC_IDENTIFIER": "test-semantic",
        },
    )
    @patch("api_extractor.get_s3_client")
    def test_upload_to_s3(self, mock_s3_client):
        """Test uploading to S3"""
        mock_s3 = MagicMock()
        mock_s3_client.return_value = mock_s3

        test_data = b'{"test": "data"}'
        result = upload_to_s3("test-bucket", test_data, "test-semantic", 0, "20240101")

        self.assertIn(
            "landing/test-semantic/downloaded_date=20240101/00000000.json", result
        )
        mock_s3.put_object.assert_called_once()

        # Check the call arguments
        call_args = mock_s3.put_object.call_args
        self.assertEqual(call_args[1]["Bucket"], "test-bucket")
        self.assertEqual(call_args[1]["Body"], test_data)
        self.assertEqual(call_args[1]["ContentType"], "application/json")
        self.assertIn("extractor", call_args[1]["Metadata"])

    def test_create_response_success(self):
        """Test successful response creation"""
        result = create_response(True, "Test message", {"key": "value"})

        self.assertEqual(result["statusCode"], 200)
        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "Test message")
        self.assertEqual(result["data"]["key"], "value")
        self.assertEqual(result["extractor"], "social-services-api-extractor")

    def test_create_response_failure(self):
        """Test failure response creation"""
        result = create_response(False, "Error message")

        self.assertEqual(result["statusCode"], 500)
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "Error message")

    @patch.dict(os.environ, {"AWS_ENDPOINT_URL": "http://localhost:4566"})
    @patch("api_extractor.boto3.client")
    def test_get_s3_client_with_endpoint(self, mock_boto_client):
        """Test S3 client creation with custom endpoint"""
        get_s3_client()
        mock_boto_client.assert_called_once_with(
            "s3", endpoint_url="http://localhost:4566"
        )

    @patch.dict(os.environ, {}, clear=True)
    @patch("api_extractor.boto3.client")
    def test_get_s3_client_without_endpoint(self, mock_boto_client):
        """Test S3 client creation with default endpoint"""
        get_s3_client()
        mock_boto_client.assert_called_once_with("s3")


if __name__ == "__main__":
    unittest.main()
