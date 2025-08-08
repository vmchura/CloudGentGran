"""
Test script for the API Extractor Lambda function
"""

import json
import os
from unittest.mock import Mock, patch, MagicMock
import sys

# Add the lambda directory to the path so we can import our function
sys.path.append(os.path.dirname(__file__))

def test_lambda_handler():
    """Test the lambda_handler function"""
    
    # Mock environment variables
    with patch.dict(os.environ, {
        'BUCKET_NAME': 'catalunya-data-dev',
        'API_URL': 'https://jsonplaceholder.typicode.com/posts',
        'API_NAME': 'jsonplaceholder'
    }):
        # Mock the requests module
        with patch('api_extractor.requests') as mock_requests:
            # Mock the S3 client
            with patch('api_extractor.s3_client') as mock_s3:
                # Set up mock responses
                mock_response = Mock()
                mock_response.json.return_value = [
                    {"id": 1, "title": "Test Post 1", "body": "Test content 1"},
                    {"id": 2, "title": "Test Post 2", "body": "Test content 2"}
                ]
                mock_response.raise_for_status.return_value = None
                mock_requests.get.return_value = mock_response
                
                mock_s3.put_object.return_value = {'ETag': '"test-etag"'}
                
                # Import and call the function
                import api_extractor
                
                # Create test event and context
                event = {}
                context = Mock()
                context.aws_request_id = 'test-request-id'
                
                # Call the function
                result = api_extractor.lambda_handler(event, context)
                
                # Verify the results
                print("Test Result:")
                print(json.dumps(result, indent=2))
                
                # Verify function calls
                mock_requests.get.assert_called_once()
                mock_s3.put_object.assert_called_once()
                
                # Check that the result indicates success
                assert result['success'] is True
                assert result['statusCode'] == 200
                assert 'data' in result
                assert result['data']['records_count'] == 2
                
                print("✅ All tests passed!")

def test_extract_from_api():
    """Test the extract_from_api function"""
    
    with patch('api_extractor.requests') as mock_requests:
        # Mock successful API response
        mock_response = Mock()
        mock_response.json.return_value = [{"test": "data"}]
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response
        
        import api_extractor
        
        result = api_extractor.extract_from_api('https://test-api.com')
        
        assert len(result) == 1
        assert result[0] == {"test": "data"}
        print("✅ extract_from_api test passed!")

def test_upload_to_s3():
    """Test the upload_to_s3 function"""
    
    with patch('api_extractor.s3_client') as mock_s3:
        mock_s3.put_object.return_value = {'ETag': '"test-etag"'}
        
        import api_extractor
        
        test_data = [{"test": "data"}]
        result = api_extractor.upload_to_s3('test-bucket', test_data, 'test-api')
        
        # Verify S3 key format
        assert result.startswith('landing/test-api/year=')
        assert 'test-api_' in result
        assert result.endswith('.json')
        
        # Verify S3 client was called
        mock_s3.put_object.assert_called_once()
        call_args = mock_s3.put_object.call_args
        
        assert call_args[1]['Bucket'] == 'test-bucket'
        assert call_args[1]['ContentType'] == 'application/json'
        
        print("✅ upload_to_s3 test passed!")

if __name__ == '__main__':
    print("🧪 Running Lambda Extractor Tests...")
    
    try:
        test_extract_from_api()
        test_upload_to_s3()
        test_lambda_handler()
        
        print("\n🎉 All tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        sys.exit(1)
