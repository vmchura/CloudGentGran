import unittest
from unittest.mock import patch, MagicMock
import json
import pandas as pd
from io import BytesIO
import os
from service_qualification_initializer import (
    lambda_handler,
    create_parquet_file,
)


class TestServiceQualificationInitializer(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "CATALOG_BUCKET_NAME": "test-bucket",
        },
    )
    @patch("service_qualification_initializer.boto3.client")
    @patch("pandas.DataFrame.to_parquet")
    def test_lambda_handler_success(self, mock_to_parquet, mock_boto_client):
        """Test successful lambda execution"""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_to_parquet.return_value = None

        event = {"table_name": "service_qualification"}
        result = lambda_handler(event, None)

        self.assertEqual(result["statusCode"], 200)
        body = json.loads(result["body"])
        self.assertEqual(body["table_name"], "service_qualification")
        self.assertIn(
            "service_qualification/service_qualification.parquet", body["s3_key"]
        )
        self.assertEqual(body["record_count"], 3)  # Number of qualifications defined

    @patch.dict(
        os.environ,
        {
            "CATALOG_BUCKET_NAME": "test-bucket",
        },
    )
    def test_lambda_handler_missing_table_name(self):
        """Test lambda handler when table_name is missing"""
        event = {}
        result = lambda_handler(event, None)

        self.assertEqual(result["statusCode"], 400)
        body = json.loads(result["body"])
        self.assertIn("error", body)
        self.assertEqual(body["error"], "table_name is required")

    @patch.dict(
        os.environ,
        {
            "CATALOG_BUCKET_NAME": "test-bucket",
        },
    )
    @patch("service_qualification_initializer.boto3.client")
    @patch("pandas.DataFrame.to_parquet")
    def test_create_parquet_file(self, mock_to_parquet, mock_boto_client):
        """Test creating parquet file"""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_to_parquet.return_value = None

        test_data = [
            {
                "service_qualification_id": "PUB-001",
                "service_qualification_description": "Public",
            },
            {
                "service_qualification_id": "PRV-001",
                "service_qualification_description": "Private",
            },
        ]

        result = create_parquet_file(mock_s3, "test-bucket", "test_table", test_data)

        self.assertEqual(result["statusCode"], 200)
        body = json.loads(result["body"])
        self.assertEqual(body["table_name"], "test_table")
        self.assertEqual(body["record_count"], 2)
        mock_s3.put_object.assert_called_once()

    @patch.dict(
        os.environ,
        {
            "CATALOG_BUCKET_NAME": "test-bucket",
        },
    )
    def test_create_parquet_file_empty_data(self):
        """Test creating parquet file with empty data"""
        mock_s3 = MagicMock()

        with self.assertRaises(ValueError) as context:
            create_parquet_file(mock_s3, "test-bucket", "test_table", [])

        self.assertIn("No data provided", str(context.exception))


if __name__ == "__main__":
    unittest.main()
