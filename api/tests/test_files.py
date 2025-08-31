import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import pandas as pd
import tempfile
import os
from app import app

client = TestClient(app)

class TestRootEndpoints:
    """Test basic root endpoints"""
    
    def test_read_root(self):
        """Test the root endpoint returns correct greeting"""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"message": "Hello from FastAPI on Cloud Run!"}
    
    def test_say_hello(self):
        """Test the hello endpoint with a name parameter"""
        response = client.get("/hello/testuser")
        assert response.status_code == 200
        assert response.json() == {"message": "Hello, testuser!"}
    
    def test_get_environment_variables(self):
        """Test the environment variables endpoint"""
        response = client.get("/env")
        assert response.status_code == 200
        assert isinstance(response.json(), dict)

class TestLLMEndpoints:
    """Test LLM-related endpoints"""
    
    @patch('app.adtiam.creds')
    @patch('app.ChatOpenAI')
    def test_get_llm(self, mock_chat_openai, mock_creds):
        """Test the LLM endpoint"""
        # Mock the LLM response
        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.return_value = "Abu Dhabi"
        mock_chat_openai.return_value = mock_llm_instance
        
        response = client.get("/utest-llm")
        assert response.status_code == 200
    
    @patch('app.adtiam.creds')
    @patch('app.ChatOpenAI')
    def test_get_llm_stream(self, mock_chat_openai, mock_creds):
        """Test the streaming LLM endpoint"""
        # Mock the LLM streaming response
        mock_llm_instance = MagicMock()
        mock_chunk = MagicMock()
        mock_chunk.content = "Test response"
        mock_llm_instance.stream.return_value = [mock_chunk]
        mock_chat_openai.return_value = mock_llm_instance
        
        payload = {"prompt": "Test prompt"}
        response = client.post("/llm", json=payload)
        assert response.status_code == 200
        assert "Test response" in response.text
    
    @patch('app.adtiam.creds')
    @patch('app.openai.OpenAI')
    def test_get_llm_native_stream(self, mock_openai, mock_creds):
        """Test the native OpenAI streaming endpoint"""
        # Mock the OpenAI client and streaming response
        mock_client_instance = MagicMock()
        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta.content = "Test content"
        mock_client_instance.chat.completions.create.return_value = [mock_chunk]
        mock_openai.return_value = mock_client_instance
        
        payload = {"prompt": "Test prompt"}
        response = client.post("/llm-openai", json=payload)
        assert response.status_code == 200
        assert "Test content" in response.text

class TestFilePreviewEndpoint:
    """Test the file preview endpoint"""
    
    @patch('app.cnxn_supabase')
    def test_preview_csv_file(self, mock_supabase):
        """Test previewing a CSV file"""
        # Mock Supabase table query response
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": "test-id", "type": "csv"}
        ]
        
        # Mock file download
        mock_supabase.storage.from_.return_value.download.return_value = b"col1,col2\nval1,val2"
        
        payload = {
            "fileid": "test-id",
            "settings": {}
        }
        
        response = client.post("/files/preview", json=payload)
        assert response.status_code == 200
        assert "data" in response.json()
    
    @patch('app.cnxn_supabase')
    def test_preview_excel_file(self, mock_supabase):
        """Test previewing an Excel file"""
        # Mock Supabase table query response
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": "test-id", "type": "excel"}
        ]
        
        # Create a temporary Excel file for testing
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            # Create a simple Excel file with pandas
            df = pd.DataFrame({'col1': ['val1'], 'col2': ['val2']})
            df.to_excel(tmp_file.name, index=False)
            tmp_file.seek(0)
            excel_content = tmp_file.read()
        
        # Mock file download
        mock_supabase.storage.from_.return_value.download.return_value = excel_content
        
        payload = {
            "fileid": "test-id",
            "settings": {}
        }
        
        response = client.post("/files/preview", json=payload)
        assert response.status_code == 200
        assert "Sheet1" in response.json()
        
        # Clean up
        os.unlink(tmp_file.name)
    
    @patch('app.cnxn_supabase')
    def test_preview_parquet_file(self, mock_supabase):
        """Test previewing a Parquet file"""
        # Mock Supabase table query response
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": "test-id", "type": "parquet"}
        ]
        
        # Create a temporary Parquet file for testing
        with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as tmp_file:
            df = pd.DataFrame({'col1': ['val1'], 'col2': ['val2']})
            df.to_parquet(tmp_file.name, index=False)
            tmp_file.seek(0)
            parquet_content = tmp_file.read()
        
        # Mock file download
        mock_supabase.storage.from_.return_value.download.return_value = parquet_content
        
        payload = {
            "fileid": "test-id",
            "settings": {}
        }
        
        response = client.post("/files/preview", json=payload)
        assert response.status_code == 200
        assert "data" in response.json()
        
        # Clean up
        os.unlink(tmp_file.name)
    
    @patch('app.cnxn_supabase')
    def test_preview_file_not_found(self, mock_supabase):
        """Test previewing a file that doesn't exist"""
        # Mock empty Supabase response
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        
        payload = {
            "fileid": "nonexistent-id",
            "settings": {}
        }
        
        response = client.post("/files/preview", json=payload)
        assert response.status_code == 404
        assert "No data source found" in response.json()["detail"]
    
    @patch('app.cnxn_supabase')
    def test_preview_unsupported_file_type(self, mock_supabase):
        """Test previewing an unsupported file type"""
        # Mock Supabase table query response with unsupported type
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": "test-id", "type": "unsupported"}
        ]
        
        payload = {
            "fileid": "test-id",
            "settings": {}
        }
        
        response = client.post("/files/preview", json=payload)
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]

class TestErrorHandling:
    """Test error handling scenarios"""
    
    def test_invalid_json_payload(self):
        """Test handling of invalid JSON payload"""
        response = client.post("/llm", data="invalid json")
        assert response.status_code == 422
    
    def test_missing_required_fields(self):
        """Test handling of missing required fields"""
        payload = {"prompt": ""}  # Missing prompt field for some endpoints
        response = client.post("/files/preview", json=payload)
        assert response.status_code == 422

if __name__ == "__main__":
    pytest.main([__file__])
