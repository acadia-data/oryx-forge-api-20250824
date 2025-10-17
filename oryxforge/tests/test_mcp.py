"""Tests for MCP tools - project management functions."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from oryxforge.services.iam import CredentialsManager


class TestMCPProjectFunctions:
    """Test MCP project management functions."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for config files."""
        with tempfile.TemporaryDirectory() as temp_path:
            yield temp_path

    @pytest.fixture
    def setup_profile(self, temp_dir):
        """Setup test profile in temporary directory."""
        creds_manager = CredentialsManager(working_dir=temp_dir)
        creds_manager.set_profile(
            user_id="test-user-123",
            project_id="test-project-456"
        )
        return temp_dir

    @pytest.fixture
    def mock_project_service(self):
        """Mock ProjectService to avoid database calls."""
        with patch('oryxforge.tools.mcp.ProjectService') as mock:
            yield mock

    def test_project_create_dataset(self, setup_profile, mock_project_service, monkeypatch):
        """Test creating a dataset via MCP."""
        # Change to temp directory
        monkeypatch.chdir(setup_profile)

        # Setup mock
        mock_instance = MagicMock()
        mock_instance.ds_create.return_value = "dataset-id-123"
        mock_project_service.return_value = mock_instance

        from oryxforge.tools.mcp import project_create_dataset

        result = project_create_dataset(name="Test Dataset")

        assert result == "dataset-id-123"
        mock_instance.ds_create.assert_called_once_with("Test Dataset")

    def test_project_create_sheet(self, setup_profile, mock_project_service, monkeypatch):
        """Test creating a datasheet via MCP."""
        monkeypatch.chdir(setup_profile)

        # Setup mock
        mock_instance = MagicMock()
        mock_instance.sheet_create.return_value = "sheet-id-789"
        mock_project_service.return_value = mock_instance

        from oryxforge.tools.mcp import project_create_sheet

        result = project_create_sheet(dataset_id="dataset-123", name="Test Sheet")

        assert result == "sheet-id-789"
        mock_instance.sheet_create.assert_called_once_with("dataset-123", "Test Sheet", source_id=None)

    def test_project_list_datasets(self, setup_profile, mock_project_service, monkeypatch):
        """Test listing datasets via MCP."""
        monkeypatch.chdir(setup_profile)

        # Setup mock
        mock_instance = MagicMock()
        mock_instance.ds_list.return_value = [
            {"id": "ds1", "name": "Dataset 1", "name_python": "dataset_1"},
            {"id": "ds2", "name": "Dataset 2", "name_python": "dataset_2"}
        ]
        mock_project_service.return_value = mock_instance

        from oryxforge.tools.mcp import project_list_datasets

        result = project_list_datasets()

        assert len(result) == 2
        assert result[0]["name"] == "Dataset 1"
        assert result[1]["name"] == "Dataset 2"
        mock_instance.ds_list.assert_called_once()

    def test_project_get_dataset(self, setup_profile, mock_project_service, monkeypatch):
        """Test getting a dataset by name via MCP."""
        monkeypatch.chdir(setup_profile)

        # Setup mock
        mock_instance = MagicMock()
        mock_instance.ds_get.return_value = {
            "id": "ds1",
            "name": "Test Dataset",
            "name_python": "test_dataset"
        }
        mock_project_service.return_value = mock_instance

        from oryxforge.tools.mcp import project_get_dataset

        result = project_get_dataset(name="Test Dataset")

        assert result["id"] == "ds1"
        assert result["name"] == "Test Dataset"
        mock_instance.ds_get.assert_called_once_with(id=None, name="Test Dataset", name_python=None)

    def test_project_list_sheets(self, setup_profile, mock_project_service, monkeypatch):
        """Test listing sheets via MCP."""
        monkeypatch.chdir(setup_profile)

        # Setup mock
        mock_instance = MagicMock()
        mock_instance.sheet_list.return_value = [
            {"id": "sh1", "name": "Sheet 1", "name_python": "sheet_1", "dataset_id": "ds1"},
            {"id": "sh2", "name": "Sheet 2", "name_python": "sheet_2", "dataset_id": "ds1"}
        ]
        mock_project_service.return_value = mock_instance

        from oryxforge.tools.mcp import project_list_sheets

        result = project_list_sheets(dataset_id="ds1")

        assert len(result) == 2
        assert result[0]["name"] == "Sheet 1"
        assert result[1]["name"] == "Sheet 2"
        mock_instance.sheet_list.assert_called_once_with("ds1", None, None)

    def test_project_get_sheet(self, setup_profile, mock_project_service, monkeypatch):
        """Test getting a sheet by name via MCP."""
        monkeypatch.chdir(setup_profile)

        # Setup mock
        mock_instance = MagicMock()
        mock_instance.sheet_get.return_value = {
            "id": "sh1",
            "name": "Test Sheet",
            "name_python": "test_sheet",
            "dataset_id": "ds1"
        }
        mock_project_service.return_value = mock_instance

        from oryxforge.tools.mcp import project_get_sheet

        result = project_get_sheet(dataset_id="ds1", name="Test Sheet")

        assert result["id"] == "sh1"
        assert result["name"] == "Test Sheet"
        mock_instance.sheet_get.assert_called_once_with(dataset_id="ds1", id=None, name="Test Sheet", name_python=None)

    def test_project_functions_use_profile(self, setup_profile, mock_project_service, monkeypatch):
        """Test that project functions use profile from CredentialsManager."""
        monkeypatch.chdir(setup_profile)

        # Setup mock
        mock_instance = MagicMock()
        mock_instance.ds_list.return_value = []
        mock_project_service.return_value = mock_instance

        from oryxforge.tools.mcp import project_list_datasets

        # Call function - it should use CredentialsManager to get user_id and project_id
        project_list_datasets()

        # Verify ProjectService was called without explicit user_id/project_id
        # (it gets them from CredentialsManager internally)
        mock_project_service.assert_called_once()

    def test_project_create_dataset_no_profile(self, temp_dir, monkeypatch):
        """Test that project functions fail without profile."""
        monkeypatch.chdir(temp_dir)

        from oryxforge.tools.mcp import project_create_dataset

        # Should raise error when no profile is configured
        with pytest.raises(ValueError, match="No profile configured"):
            project_create_dataset(name="Test Dataset")


if __name__ == '__main__':
    pytest.main([__file__])
