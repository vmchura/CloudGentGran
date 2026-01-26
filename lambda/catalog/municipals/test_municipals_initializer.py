import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import pandas as pd
from io import BytesIO
import os
from municipals_initializer import (
    lambda_handler,
    upload_to_s3,
    upload_dataframe_to_s3,
    process_municipal_data,
    create_response,
    get_s3_client,
)


class TestMunicipalsInitializer(unittest.TestCase):
    def test_process_municipal_data_complete(self):
        """Test processing when all expected columns are present"""
        json_data = [
            {
                "codi": "001",
                "nom": "Municipality1",
                "codi_comarca": "01",
                "nom_comarca": "Comarca1",
            },
            {
                "codi": "002",
                "nom": "Municipality2",
                "codi_comarca": "02",
                "nom_comarca": "Comarca2",
            },
        ]

        result = process_municipal_data(json_data)

        # Check that all columns are renamed correctly
        self.assertIn("municipal_id", result.columns)
        self.assertIn("municipal_name", result.columns)
        self.assertIn("comarca_id", result.columns)
        self.assertIn("comarca_name", result.columns)

        # Check that original columns are not present
        self.assertNotIn("codi", result.columns)
        self.assertNotIn("nom", result.columns)
        self.assertNotIn("codi_comarca", result.columns)
        self.assertNotIn("nom_comarca", result.columns)

        # Check data values
        self.assertEqual(result.iloc[0]["municipal_id"], "001")
        self.assertEqual(result.iloc[0]["municipal_name"], "Municipality1")
        self.assertEqual(result.iloc[0]["comarca_id"], "01")
        self.assertEqual(result.iloc[0]["comarca_name"], "Comarca1")

    def test_process_municipal_data_partial_columns(self):
        """Test processing when only some expected columns are present"""
        json_data = [
            {"codi": "001", "nom": "Municipality1"},
            {"codi": "002", "nom": "Municipality2"},
        ]

        result = process_municipal_data(json_data)

        # Check that existing columns are renamed
        self.assertIn("municipal_id", result.columns)
        self.assertIn("municipal_name", result.columns)

        # Check that missing columns are not created
        self.assertNotIn("comarca_id", result.columns)
        self.assertNotIn("comarca_name", result.columns)

    def test_process_municipal_data_no_expected_columns(self):
        """Test processing when no expected columns are present"""
        json_data = [{"other_field": "value1"}, {"other_field": "value2"}]

        result = process_municipal_data(json_data)

        # Should only contain the original columns that weren't filtered
        self.assertIn("other_field", result.columns)
        self.assertEqual(len(result.columns), 1)

    def test_process_municipal_data_empty_list(self):
        """Test processing when data list is empty"""
        result = process_municipal_data([])

        # Should return empty DataFrame
        self.assertEqual(len(result), 0)
        self.assertIsInstance(result, pd.DataFrame)

    @patch.dict(
        os.environ,
        {
            "CATALOG_BUCKET_NAME": "test-bucket",
            "DATASET_IDENTIFIER": "test-dataset",
            "SEMANTIC_IDENTIFIER": "test-municipals",
        },
    )
    @patch("municipals_initializer.get_s3_client")
    @patch("pandas.DataFrame.to_parquet")
    def test_upload_dataframe_to_s3(self, mock_to_parquet, mock_s3_client):
        """Test uploading DataFrame to S3"""
        mock_s3 = MagicMock()
        mock_s3_client.return_value = mock_s3

        # Mock the to_parquet method to avoid fastparquet dependency
        mock_to_parquet.return_value = None

        df = pd.DataFrame(
            {
                "municipal_id": ["001", "002"],
                "municipal_name": ["Municipality1", "Municipality2"],
                "comarca_id": ["01", "02"],
            }
        )

        result = upload_dataframe_to_s3("test-bucket", df, "test-table")

        self.assertEqual(result, "test-table/municipals.parquet")
        mock_s3.put_object.assert_called_once()

        # Check the call arguments
        call_args = mock_s3.put_object.call_args
        self.assertEqual(call_args[1]["Bucket"], "test-bucket")
        self.assertEqual(call_args[1]["Key"], "test-table/municipals.parquet")
        self.assertEqual(call_args[1]["ContentType"], "application/octet-stream")
        self.assertIn("record_count", call_args[1]["Metadata"])
        self.assertIn("created_at", call_args[1]["Metadata"])

    @patch.dict(
        os.environ,
        {
            "CATALOG_BUCKET_NAME": "test-bucket",
            "DATASET_IDENTIFIER": "test-dataset",
            "SEMANTIC_IDENTIFIER": "test-municipals",
        },
    )
    @patch("municipals_initializer.upload_dataframe_to_s3")
    @patch("municipals_initializer.get_s3_client")
    @patch("pandas.DataFrame.to_parquet")
    def test_upload_to_s3(self, mock_to_parquet, mock_s3_client, mock_upload_dataframe):
        """Test the complete upload_to_s3 function"""
        mock_s3 = MagicMock()
        mock_s3_client.return_value = mock_s3
        mock_upload_dataframe.return_value = "test-municipals/municipals.parquet"

        # Mock S3 get_object response for metadata update
        mock_response = {"Body": MagicMock()}
        mock_response["Body"].read.return_value = b"mock_parquet_data"
        mock_s3.get_object.return_value = mock_response

        json_data = [
            {"codi": "001", "nom": "Municipality1", "codi_comarca": "01"},
            {"codi": "002", "nom": "Municipality2", "codi_comarca": "02"},
        ]

        result = upload_to_s3("test-bucket", json_data, "test-municipals", "20240101")

        self.assertEqual(result, "test-municipals/municipals.parquet")
        mock_upload_dataframe.assert_called_once()

        # Check that the upload_dataframe_to_s3 was called with processed data
        call_args = mock_upload_dataframe.call_args
        processed_df = call_args[0][1]  # Second argument is the DataFrame

        # Verify the DataFrame was processed (columns renamed)
        self.assertIn("municipal_id", processed_df.columns)
        self.assertIn("municipal_name", processed_df.columns)
        self.assertNotIn("codi", processed_df.columns)

    @patch.dict(os.environ, {"AWS_ENDPOINT_URL": "http://localhost:4566"})
    @patch("municipals_initializer.boto3.client")
    def test_get_s3_client_with_endpoint(self, mock_boto_client):
        """Test S3 client creation with custom endpoint"""
        get_s3_client()
        mock_boto_client.assert_called_once_with(
            "s3", endpoint_url="http://localhost:4566"
        )

    @patch.dict(os.environ, {}, clear=True)
    @patch("municipals_initializer.boto3.client")
    def test_get_s3_client_without_endpoint(self, mock_boto_client):
        """Test S3 client creation with default endpoint"""
        get_s3_client()
        mock_boto_client.assert_called_once_with("s3")

    def test_create_response_success(self):
        """Test successful response creation"""
        result = create_response(True, "Test message", {"key": "value"})

        self.assertEqual(result["statusCode"], 200)
        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "Test message")
        self.assertEqual(result["data"]["key"], "value")

    def test_create_response_failure(self):
        """Test failure response creation"""
        result = create_response(False, "Error message")

        self.assertEqual(result["statusCode"], 500)
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "Error message")

    @patch.dict(
        os.environ,
        {
            "CATALOG_BUCKET_NAME": "test-bucket",
            "DATASET_IDENTIFIER": "test-dataset",
            "SEMANTIC_IDENTIFIER": "test-municipals",
        },
    )
    @patch("municipals_initializer.upload_to_s3")
    @patch("municipals_initializer.urllib.request.urlopen")
    def test_lambda_handler_success(self, mock_urlopen, mock_upload):
        """Test successful lambda execution"""
        # Mock the API responses
        mock_responses = [
            [
                {"codi": "001", "nom": "Municipality1", "codi_comarca": "01"}
            ],  # First iteration
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
        mock_upload.return_value = "test-municipals/municipals.parquet"

        result = lambda_handler({}, None)

        self.assertEqual(result["statusCode"], 200)
        self.assertTrue(result["success"])
        self.assertIn("data", result)
        self.assertEqual(result["data"]["total_records"], 1)
        self.assertEqual(result["data"]["s3_key"], "test-municipals/municipals.parquet")

    @patch.dict(
        os.environ,
        {
            "CATALOG_BUCKET_NAME": "test-bucket",
            "DATASET_IDENTIFIER": "test-dataset",
            "SEMANTIC_IDENTIFIER": "test-municipals",
        },
    )
    @patch("municipals_initializer.urllib.request.urlopen")
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


if __name__ == "__main__":
    unittest.main()
