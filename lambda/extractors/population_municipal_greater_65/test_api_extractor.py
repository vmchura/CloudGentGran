import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
from api_extractor import lambda_handler, upload_to_s3, create_response, get_s3_client
import os


class TestLambdaFunction(unittest.TestCase):

    @patch.dict(os.environ, {'BUCKET_NAME': 'test-bucket', 'SEMANTIC_IDENTIFIER': 'test-id'})
    @patch('api_extractor.get_s3_client')
    @patch('api_extractor.urllib.request.urlopen')
    @patch('api_extractor.time.sleep')
    def test_lambda_handler_success(self, mock_sleep, mock_urlopen, mock_s3_client):
        mock_sleep.return_value = None

        mock_s3 = MagicMock()
        mock_s3_client.return_value = mock_s3

        mock_responses = [
            {'link': {'item': [{'label': 'Cens de població i habitatges', 'href': 'http://api/pop'}]}},
            {'link': {'item': [{'label': 'Població. Per sexe i edat en grans grups', 'href': 'http://api/age'}]}},
            {'link': {'item': [{'href': 'http://api/table'}]}},
            {'link': {'item': [{'label': 'Per municipis', 'href': 'http://api/municipal'}]}},
            {'dimension': {'YEAR': {'category': {'index': {'2020': 0, '2021': 1}}}}},
            {'value': [100, 200]},
            {'value': [150, 250]},
        ]

        mock_contexts = []
        for resp in mock_responses:
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps(resp).encode('utf-8')
            mock_cm = MagicMock()
            mock_cm.__enter__.return_value = mock_response
            mock_cm.__exit__.return_value = False
            mock_contexts.append(mock_cm)

        mock_urlopen.side_effect = mock_contexts

        result = lambda_handler({}, None)
        self.assertEqual(result['statusCode'], 200)
        self.assertTrue(result['success'])


    @patch.dict(os.environ, {'BUCKET_NAME': 'test-bucket', 'SEMANTIC_IDENTIFIER': 'test-id'})
    @patch('api_extractor.get_s3_client')
    def test_upload_to_s3(self, mock_s3_client):
        mock_s3 = MagicMock()
        mock_s3_client.return_value = mock_s3

        test_data = b'{"test": "data"}'
        result = upload_to_s3('test-bucket', test_data, 'test-id', '2020')

        self.assertEqual(result, 'landing/test-id/2020.json')
        mock_s3.put_object.assert_called_once()

    def test_create_response_success(self):
        result = create_response(True, "Test message", {'key': 'value'})

        self.assertEqual(result['statusCode'], 200)
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], "Test message")
        self.assertEqual(result['data']['key'], 'value')

    def test_create_response_failure(self):
        result = create_response(False, "Error message")

        self.assertEqual(result['statusCode'], 500)
        self.assertFalse(result['success'])
        self.assertEqual(result['message'], "Error message")

    @patch.dict(os.environ, {'AWS_ENDPOINT_URL': 'http://localhost:4566'})
    @patch('api_extractor.boto3.client')
    def test_get_s3_client_with_endpoint(self, mock_boto_client):
        get_s3_client()
        mock_boto_client.assert_called_once_with('s3', endpoint_url='http://localhost:4566')

    @patch.dict(os.environ, {}, clear=True)
    @patch('api_extractor.boto3.client')
    def test_get_s3_client_without_endpoint(self, mock_boto_client):
        get_s3_client()
        mock_boto_client.assert_called_once_with('s3')


if __name__ == '__main__':
    unittest.main()