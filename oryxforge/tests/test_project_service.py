"""Tests for ProjectService."""

import pytest
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

from ..services.project_service import ProjectService


class TestProjectService:
    """Test cases for ProjectService."""

    @pytest.fixture
    def mock_supabase_client(self):
        """Mock Supabase client."""
        mock_client = Mock()
        # Mock project validation
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {"id": "test-project-id", "name": "Test Project"}
        ]
        return mock_client

    @pytest.fixture
    def mock_gcs(self):
        """Mock GCS filesystem."""
        mock_gcs = Mock()
        mock_gcs.open.return_value.__enter__ = Mock()
        mock_gcs.open.return_value.__exit__ = Mock()
        return mock_gcs

    @pytest.fixture
    def project_service(self, mock_supabase_client, mock_gcs):
        """Create ProjectService instance with mocked dependencies."""
        with patch.object(ProjectService, '_init_supabase_client', return_value=mock_supabase_client):
            with patch('gcsfs.GCSFileSystem', return_value=mock_gcs):
                with patch.object(ProjectService, '_validate_project'):
                    service = ProjectService('test-project-id', 'test-user-id')
                    service.project_name = 'Test Project'
                    return service

    def test_init_success(self, mock_supabase_client):
        """Test successful initialization."""
        with patch.object(ProjectService, '_init_supabase_client', return_value=mock_supabase_client):
            with patch('gcsfs.GCSFileSystem'):
                service = ProjectService('test-project-id', 'test-user-id')
                assert service.project_id == 'test-project-id'
                assert service.user_id == 'test-user-id'

    def test_init_gcs_error(self, mock_supabase_client):
        """Test initialization with GCS error."""
        with patch.object(ProjectService, '_init_supabase_client', return_value=mock_supabase_client):
            with patch('gcsfs.GCSFileSystem', side_effect=Exception("GCS error")):
                service = ProjectService('test-project-id', 'test-user-id')
                assert service.gcs is None

    def test_init_supabase_client_missing_credentials(self):
        """Test Supabase client initialization with missing credentials."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="Supabase credentials not found"):
                ProjectService._init_supabase_client(ProjectService)

    def test_validate_project_success(self, mock_supabase_client):
        """Test successful project validation."""
        with patch.object(ProjectService, '_init_supabase_client', return_value=mock_supabase_client):
            with patch('gcsfs.GCSFileSystem'):
                service = ProjectService('test-project-id', 'test-user-id')
                assert service.project_name == 'Test Project'

    def test_validate_project_not_found(self, mock_supabase_client):
        """Test project validation with non-existing project."""
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []

        with patch.object(ProjectService, '_init_supabase_client', return_value=mock_supabase_client):
            with patch('gcsfs.GCSFileSystem'):
                with pytest.raises(ValueError, match="Project test-project-id not found"):
                    ProjectService('test-project-id', 'test-user-id')

    def test_ds_list_success(self, project_service):
        """Test successful dataset listing."""
        mock_datasets = [
            {'id': 'dataset-1', 'name': 'Dataset 1'},
            {'id': 'dataset-2', 'name': 'Dataset 2'}
        ]
        project_service.supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value.data = mock_datasets

        result = project_service.ds_list()
        assert result == mock_datasets

    def test_ds_list_database_error(self, project_service):
        """Test dataset listing with database error."""
        project_service.supabase_client.table.side_effect = Exception("Database error")

        with pytest.raises(ValueError, match="Failed to list datasets"):
            project_service.ds_list()

    def test_ds_create_success(self, project_service):
        """Test successful dataset creation."""
        project_service.supabase_client.table.return_value.insert.return_value.execute.return_value.data = [
            {'id': 'new-dataset-id'}
        ]

        result = project_service.ds_create('Test Dataset')
        assert result == 'new-dataset-id'

    def test_ds_create_duplicate_name(self, project_service):
        """Test dataset creation with duplicate name."""
        project_service.supabase_client.table.return_value.insert.return_value.execute.side_effect = \
            Exception("unique_user_dataset_name")

        with pytest.raises(ValueError, match="Dataset 'Test Dataset' already exists"):
            project_service.ds_create('Test Dataset')

    def test_ds_create_database_error(self, project_service):
        """Test dataset creation with database error."""
        project_service.supabase_client.table.return_value.insert.return_value.execute.return_value.data = []

        with pytest.raises(ValueError, match="Failed to create dataset"):
            project_service.ds_create('Test Dataset')

    def test_sheet_create_success(self, project_service):
        """Test successful datasheet creation."""
        # Mock ds_exists
        with patch.object(project_service, 'ds_exists', return_value=True):
            project_service.supabase_client.table.return_value.insert.return_value.execute.return_value.data = [
                {'id': 'new-sheet-id'}
            ]

            result = project_service.sheet_create('test-dataset-id', 'Test Sheet')
            assert result == 'new-sheet-id'

    def test_sheet_create_dataset_not_found(self, project_service):
        """Test datasheet creation with non-existing dataset."""
        with patch.object(project_service, 'ds_exists', return_value=False):
            with pytest.raises(ValueError, match="Dataset test-dataset-id not found"):
                project_service.sheet_create('test-dataset-id', 'Test Sheet')

    def test_sheet_create_duplicate_name(self, project_service):
        """Test datasheet creation with duplicate name."""
        with patch.object(project_service, 'ds_exists', return_value=True):
            project_service.supabase_client.table.return_value.insert.return_value.execute.side_effect = \
                Exception("unique_user_dataset_datasheet_name")

            with pytest.raises(ValueError, match="Datasheet 'Test Sheet' already exists"):
                project_service.sheet_create('test-dataset-id', 'Test Sheet')

    def test_sheet_list_specific_dataset(self, project_service):
        """Test datasheet listing for specific dataset."""
        mock_sheets = [
            {'id': 'sheet-1', 'name': 'Sheet 1', 'dataset_id': 'dataset-1'},
            {'id': 'sheet-2', 'name': 'Sheet 2', 'dataset_id': 'dataset-1'}
        ]
        project_service.supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value.data = mock_sheets

        result = project_service.sheet_list('dataset-1')
        assert result == mock_sheets

    def test_sheet_list_all_datasets(self, project_service):
        """Test datasheet listing for all datasets."""
        mock_datasets = [{'id': 'dataset-1'}, {'id': 'dataset-2'}]
        mock_sheets = [
            {'id': 'sheet-1', 'name': 'Sheet 1', 'dataset_id': 'dataset-1'},
            {'id': 'sheet-2', 'name': 'Sheet 2', 'dataset_id': 'dataset-2'}
        ]

        with patch.object(project_service, 'ds_list', return_value=mock_datasets):
            project_service.supabase_client.table.return_value.select.return_value.eq.return_value.in_.return_value.order.return_value.execute.return_value.data = mock_sheets

            result = project_service.sheet_list()
            assert result == mock_sheets

    def test_sheet_list_no_datasets(self, project_service):
        """Test datasheet listing with no datasets."""
        with patch.object(project_service, 'ds_list', return_value=[]):
            result = project_service.sheet_list()
            assert result == []

    @patch('subprocess.run')
    def test_project_init_new_repo(self, mock_subprocess, project_service):
        """Test project initialization with new git repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            with patch('pathlib.Path.cwd', return_value=temp_path):
                # Mock git commands
                mock_subprocess.return_value = Mock()

                project_service.project_init()

                # Verify git commands were called
                assert mock_subprocess.call_count >= 3  # init, add, commit

                # Verify .gitignore was created
                assert (temp_path / '.gitignore').exists()

    @patch('subprocess.run')
    def test_project_init_existing_repo(self, mock_subprocess, project_service):
        """Test project initialization with existing git repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / '.git').mkdir()  # Create .git directory

            with patch('pathlib.Path.cwd', return_value=temp_path):
                project_service.project_init()

                # Git init should not be called for existing repo
                mock_subprocess.assert_not_called()

    @patch('subprocess.run')
    def test_project_init_git_error(self, mock_subprocess, project_service):
        """Test project initialization with git error."""
        mock_subprocess.side_effect = subprocess.CalledProcessError(1, 'git', stderr=b'Git error')

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('pathlib.Path.cwd', return_value=Path(temp_dir)):
                with pytest.raises(ValueError, match="Git operation failed"):
                    project_service.project_init()

    def test_ds_init_success(self, project_service):
        """Test successful dataset initialization."""
        with patch.object(project_service, 'ds_exists', return_value=True):
            project_service.supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
                {'name': 'Test Dataset'}
            ]

            # Should not raise an exception
            project_service.ds_init('test-dataset-id')

    def test_ds_init_not_found(self, project_service):
        """Test dataset initialization with non-existing dataset."""
        with patch.object(project_service, 'ds_exists', return_value=False):
            with pytest.raises(ValueError, match="Dataset test-dataset-id not found"):
                project_service.ds_init('test-dataset-id')

    def test_ds_exists_true(self, project_service):
        """Test ds_exists returns True for existing dataset."""
        project_service.supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {'id': 'test-dataset-id'}
        ]

        result = project_service.ds_exists('test-dataset-id')
        assert result is True

    def test_ds_exists_false(self, project_service):
        """Test ds_exists returns False for non-existing dataset."""
        project_service.supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = []

        result = project_service.ds_exists('non-existing-id')
        assert result is False

    def test_ds_exists_exception(self, project_service):
        """Test ds_exists returns False on exception."""
        project_service.supabase_client.table.side_effect = Exception("Database error")

        result = project_service.ds_exists('test-dataset-id')
        assert result is False

    def test_sheet_init_success(self, project_service):
        """Test successful datasheet initialization."""
        with patch.object(project_service, 'sheet_exists', return_value=True):
            project_service.supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
                {'name': 'Test Sheet', 'dataset_id': 'test-dataset-id'}
            ]

            # Mock GCS operations
            mock_file = Mock()
            project_service.gcs.open.return_value.__enter__.return_value = mock_file

            # Mock DataFrame.to_parquet
            with patch('pandas.DataFrame.to_parquet'):
                project_service.sheet_init('test-sheet-id')

            # Verify update was called
            project_service.supabase_client.table.return_value.update.assert_called()

    def test_sheet_init_not_found(self, project_service):
        """Test datasheet initialization with non-existing sheet."""
        with patch.object(project_service, 'sheet_exists', return_value=False):
            with pytest.raises(ValueError, match="Datasheet test-sheet-id not found"):
                project_service.sheet_init('test-sheet-id')

    def test_sheet_init_no_gcs(self, project_service):
        """Test datasheet initialization without GCS."""
        project_service.gcs = None

        with patch.object(project_service, 'sheet_exists', return_value=True):
            with pytest.raises(ValueError, match="GCS filesystem not available"):
                project_service.sheet_init('test-sheet-id')

    def test_sheet_exists_true(self, project_service):
        """Test sheet_exists returns True for existing sheet."""
        project_service.supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {'id': 'test-sheet-id'}
        ]

        result = project_service.sheet_exists('test-sheet-id')
        assert result is True

    def test_sheet_exists_false(self, project_service):
        """Test sheet_exists returns False for non-existing sheet."""
        project_service.supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []

        result = project_service.sheet_exists('non-existing-id')
        assert result is False

    @patch('subprocess.run')
    def test_git_pull_new_repo(self, mock_subprocess, project_service):
        """Test git pull with new repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            target_path = Path(temp_dir) / 'project'

            project_service.git_pull(str(target_path))

            # Verify directory was created
            assert target_path.exists()

            # Verify git init was called
            mock_subprocess.assert_called_once()

    @patch('subprocess.run')
    def test_git_pull_existing_repo(self, mock_subprocess, project_service):
        """Test git pull with existing repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            target_path = Path(temp_dir) / 'project'
            target_path.mkdir()
            (target_path / '.git').mkdir()

            project_service.git_pull(str(target_path))

            # Git init should not be called for existing repo
            mock_subprocess.assert_not_called()

    @patch('subprocess.run')
    def test_git_pull_error(self, mock_subprocess, project_service):
        """Test git pull with subprocess error."""
        mock_subprocess.side_effect = subprocess.CalledProcessError(1, 'git', stderr=b'Git error')

        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(ValueError, match="Git operation failed"):
                project_service.git_pull(temp_dir)

    def test_is_initialized_true(self, project_service):
        """Test is_initialized returns True for initialized project."""
        result = project_service.is_initialized()
        assert result is True

    def test_is_initialized_false(self, project_service):
        """Test is_initialized returns False for uninitialized project."""
        project_service.project_id = None
        result = project_service.is_initialized()
        assert result is False

    def test_get_default_dataset_id_success(self, project_service):
        """Test successful default dataset retrieval."""
        project_service.supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {'id': 'scratchpad-id'}
        ]

        result = project_service.get_default_dataset_id()
        assert result == 'scratchpad-id'

    def test_get_default_dataset_id_not_found(self, project_service):
        """Test default dataset retrieval when not found."""
        project_service.supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = []

        with pytest.raises(ValueError, match="Scratchpad dataset not found"):
            project_service.get_default_dataset_id()

    def test_get_first_sheet_id_success(self, project_service):
        """Test successful first sheet retrieval."""
        mock_sheets = [{'id': 'first-sheet-id', 'name': 'Sheet 1'}]

        with patch.object(project_service, 'sheet_list', return_value=mock_sheets):
            result = project_service.get_first_sheet_id('test-dataset-id')
            assert result == 'first-sheet-id'

    def test_get_first_sheet_id_no_sheets(self, project_service):
        """Test first sheet retrieval with no sheets."""
        with patch.object(project_service, 'sheet_list', return_value=[]):
            with pytest.raises(ValueError, match="No datasheets found"):
                project_service.get_first_sheet_id('test-dataset-id')

    def test_interactive_dataset_select_success(self, project_service):
        """Test successful interactive dataset selection."""
        mock_datasets = [
            {'id': 'dataset-1', 'name': 'Dataset 1'},
            {'id': 'dataset-2', 'name': 'Dataset 2'}
        ]

        with patch.object(project_service, 'ds_list', return_value=mock_datasets):
            with patch('builtins.input', return_value='1'):
                result = project_service.interactive_dataset_select()
                assert result == 'dataset-1'

    def test_interactive_dataset_select_no_datasets(self, project_service):
        """Test interactive dataset selection with no datasets."""
        with patch.object(project_service, 'ds_list', return_value=[]):
            with pytest.raises(ValueError, match="No datasets found"):
                project_service.interactive_dataset_select()

    def test_interactive_sheet_select_success(self, project_service):
        """Test successful interactive sheet selection."""
        mock_sheets = [
            {'id': 'sheet-1', 'name': 'Sheet 1'},
            {'id': 'sheet-2', 'name': 'Sheet 2'}
        ]

        with patch.object(project_service, 'sheet_list', return_value=mock_sheets):
            with patch('builtins.input', return_value='1'):
                result = project_service.interactive_sheet_select()
                assert result == 'sheet-1'

    def test_interactive_sheet_select_no_sheets(self, project_service):
        """Test interactive sheet selection with no sheets."""
        with patch.object(project_service, 'sheet_list', return_value=[]):
            with pytest.raises(ValueError, match="No datasheets found"):
                project_service.interactive_sheet_select()

    def test_find_dataset_by_name_success(self, project_service):
        """Test successful dataset finding by name."""
        project_service.supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {'id': 'found-dataset-id'}
        ]

        result = project_service.find_dataset_by_name('Test Dataset')
        assert result == 'found-dataset-id'

    def test_find_dataset_by_name_not_found(self, project_service):
        """Test dataset finding by name when not found."""
        project_service.supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = []

        with pytest.raises(ValueError, match="Dataset 'Test Dataset' not found"):
            project_service.find_dataset_by_name('Test Dataset')

    def test_find_sheet_by_name_with_dataset(self, project_service):
        """Test successful sheet finding by name with dataset ID."""
        project_service.supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {'id': 'found-sheet-id'}
        ]

        result = project_service.find_sheet_by_name('Test Sheet', 'test-dataset-id')
        assert result == 'found-sheet-id'

    def test_find_sheet_by_name_all_datasets(self, project_service):
        """Test sheet finding by name across all datasets."""
        mock_datasets = [{'id': 'dataset-1'}, {'id': 'dataset-2'}]

        with patch.object(project_service, 'ds_list', return_value=mock_datasets):
            project_service.supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.in_.return_value.execute.return_value.data = [
                {'id': 'found-sheet-id'}
            ]

            result = project_service.find_sheet_by_name('Test Sheet')
            assert result == 'found-sheet-id'

    def test_find_sheet_by_name_not_found(self, project_service):
        """Test sheet finding by name when not found."""
        project_service.supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = []

        with pytest.raises(ValueError, match="Datasheet 'Test Sheet' not found"):
            project_service.find_sheet_by_name('Test Sheet', 'test-dataset-id')


if __name__ == '__main__':
    pytest.main([__file__])