import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from services.file_service import FileService


class TestFileService:
    """Test cases for FileService class."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.mock_supabase = Mock()
        self.file_service = FileService(self.mock_supabase)
    
    def test_get_data_source_record_success(self):
        """Test successful retrieval of data source record."""
        # Arrange
        mock_response = Mock()
        mock_response.data = [{"id": "test123", "type": "csv"}]
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        
        # Act
        result = self.file_service.get_data_source_record("test123")
        
        # Assert
        assert result == {"id": "test123", "type": "csv"}
        self.mock_supabase.table.assert_called_with("data_sources")
    
    def test_get_data_source_record_not_found(self):
        """Test error when data source record is not found."""
        # Arrange
        mock_response = Mock()
        mock_response.data = []
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        
        # Act & Assert
        with pytest.raises(ValueError, match="No data source found for fileid: test123"):
            self.file_service.get_data_source_record("test123")
    
    @patch('os.makedirs')
    @patch('builtins.open', create=True)
    def test_download_file_success(self, mock_open, mock_makedirs):
        # Arrange
        mock_file_response = b"test file content"
        self.mock_supabase.storage.from_.return_value.download.return_value = mock_file_response
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Act
        result = self.file_service.download_file("test123", "/data/test123")
        
        # Assert
        assert result == "/data/test123/file"
        mock_makedirs.assert_called_with("/data/test123", exist_ok=True)
        mock_file.write.assert_called_with(mock_file_response)
    
    def test_read_file_preview_csv(self):
        """Test reading CSV file preview."""
        # Arrange
        test_data = pd.DataFrame({'col1': [1, 2, 3], 'col2': ['a', 'b', 'c']})
        
        with patch('pandas.read_csv', return_value=test_data):
            # Act
            result = self.file_service.read_file_preview("/path/to/file.csv", "csv")
            
            # Assert
            assert "data" in result
            assert len(result["data"]) == 3
            assert result["data"][0] == {"col1": 1, "col2": "a"}
    
    def test_read_file_preview_excel(self):
        """Test reading Excel file preview."""
        # Arrange
        test_data1 = pd.DataFrame({'col1': [1, 2], 'col2': ['a', 'b']})
        test_data2 = pd.DataFrame({'col3': [3, 4], 'col4': ['c', 'd']})
        
        mock_excel_file = Mock()
        mock_excel_file.sheet_names = ["Sheet1", "Sheet2"]
        
        with patch('pandas.ExcelFile', return_value=mock_excel_file), \
             patch('pandas.read_excel', side_effect=[test_data1, test_data2]):
            
            # Act
            result = self.file_service.read_file_preview("/path/to/file.xlsx", "excel")
            
            # Assert
            assert "Sheet1" in result
            assert "Sheet2" in result
            assert len(result["Sheet1"]) == 2
            assert len(result["Sheet2"]) == 2
    
    def test_read_file_preview_parquet(self):
        """Test reading Parquet file preview."""
        # Arrange
        test_data = pd.DataFrame({'col1': [1, 2, 3], 'col2': ['a', 'b', 'c']})
        
        with patch('pandas.read_parquet', return_value=test_data):
            # Act
            result = self.file_service.read_file_preview("/path/to/file.parquet", "parquet")
            
            # Assert
            assert "data" in result
            assert len(result["data"]) == 3
    
    def test_read_file_preview_unsupported_type(self):
        """Test error when file type is unsupported."""
        # Act & Assert
        with pytest.raises(ValueError, match="Unsupported file type: txt"):
            self.file_service.read_file_preview("/path/to/file.txt", "txt")
    
    @patch('os.path.exists')
    @patch('os.remove')
    def test_cleanup_file_exists(self, mock_remove, mock_exists):
        """Test cleanup when file exists."""
        # Arrange
        mock_exists.return_value = True
        
        # Act
        self.file_service.cleanup_file("/path/to/file")
        
        # Assert
        mock_remove.assert_called_with("/path/to/file")
    
    @patch('os.path.exists')
    @patch('os.remove')
    def test_cleanup_file_not_exists(self, mock_remove, mock_exists):
        """Test cleanup when file doesn't exist."""
        # Arrange
        mock_exists.return_value = False
        
        # Act
        self.file_service.cleanup_file("/path/to/file")
        
        # Assert
        mock_remove.assert_not_called()
    
    @patch.object(FileService, 'get_data_source_record')
    @patch.object(FileService, 'download_file')
    @patch.object(FileService, 'read_file_preview')
    @patch.object(FileService, 'cleanup_file')
    def test_preview_file_success(self, mock_cleanup, mock_read, mock_download, mock_get_record):
        """Test successful file preview workflow."""
        # Arrange
        mock_get_record.return_value = {"id": "test123", "type": "csv"}
        mock_download.return_value = "/data/test123/file"
        mock_read.return_value = {"data": [{"col1": 1, "col2": "a"}]}
        
        # Act
        result = self.file_service.preview_file("test123")
        
        # Assert
        assert result == {"data": [{"col1": 1, "col2": "a"}]}
        mock_get_record.assert_called_with("test123")
        mock_download.assert_called_with("test123", "/data/test123")
        mock_read.assert_called_with("/data/test123/file", "csv")
        mock_cleanup.assert_called_with("/data/test123/file")
    
    @patch.object(FileService, 'get_data_source_record')
    @patch.object(FileService, 'download_file')
    @patch.object(FileService, 'cleanup_file')
    def test_preview_file_cleanup_on_error(self, mock_cleanup, mock_download, mock_get_record):
        """Test that cleanup happens even when an error occurs."""
        # Arrange
        mock_get_record.return_value = {"id": "test123", "type": "csv"}
        mock_download.return_value = "/data/test123/file"
        mock_get_record.side_effect = ValueError("Test error")
        
        # Act & Assert
        with pytest.raises(ValueError, match="Test error"):
            self.file_service.preview_file("test123")
        
        # Cleanup should still be called
        mock_cleanup.assert_called_with("/data/test123/file")


if __name__ == "__main__":
    pytest.main([__file__])
