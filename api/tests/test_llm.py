import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import pandas as pd
import tempfile
import os
import sys

# Add the parent directory to the path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    @patch('langchain_openai.ChatOpenAI')
    def test_get_llm(self, mock_chat_openai, mock_creds):
        """Test the LLM endpoint"""
        # Mock the LLM response
        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.return_value = "Abu Dhabi"
        mock_chat_openai.return_value = mock_llm_instance
        
        response = client.get("/utest-llm")
        assert response.status_code == 200
    
    @patch('app.adtiam.creds')
    @patch('langchain_openai.ChatOpenAI')
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
    @patch('openai.OpenAI')
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
