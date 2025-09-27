"""Tests for CLIService."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from configobj import ConfigObj

from ..services.cli_service import CLIService


class TestCLIService:
    """Test cases for CLIService."""

    @pytest.fixture
    def mock_supabase_client(self):
        """Mock Supabase client."""
        mock_client = Mock()
        mock_client.auth.admin.get_user_by_id.return_value.user = {"id": "test-user-id"}
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": "test-id"}
        ]
        return mock_client

    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary directory for config files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def cli_service(self, mock_supabase_client, temp_config_dir):
        """Create CLIService instance with mocked dependencies."""
        with patch.object(CLIService, '_init_supabase_client', return_value=mock_supabase_client):
            with patch.object(CLIService, 'config_dir', temp_config_dir):
                # Create config file with user ID
                config_file = temp_config_dir / 'cfg.ini'
                config = ConfigObj()
                config['user'] = {'userid': 'test-user-id'}
                config.filename = str(config_file)
                config.write()

                service = CLIService()
                return service

    def test_init_with_user_id(self, mock_supabase_client):
        """Test initialization with explicit user ID."""
        with patch.object(CLIService, '_init_supabase_client', return_value=mock_supabase_client):
            service = CLIService(user_id='test-user-id')
            assert service.user_id == 'test-user-id'

    def test_init_without_config_raises_error(self, mock_supabase_client):
        """Test initialization without config raises error."""
        with patch.object(CLIService, '_init_supabase_client', return_value=mock_supabase_client):
            with patch.object(CLIService, 'get_user_config', return_value={}):
                with pytest.raises(ValueError, match="No user ID configured"):
                    CLIService()

    def test_init_supabase_client_missing_credentials(self):
        """Test Supabase client initialization with missing credentials."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="Supabase credentials not found"):
                CLIService._init_supabase_client(CLIService)

    @patch.dict('os.environ', {'SUPABASE_URL': 'test-url', 'SUPABASE_ANON_KEY': 'test-key'})
    @patch('oryxforge.services.cli_service.create_client')
    def test_init_supabase_client_success(self, mock_create_client):
        """Test successful Supabase client initialization."""
        mock_client = Mock()
        mock_create_client.return_value = mock_client

        result = CLIService._init_supabase_client(CLIService)
        assert result == mock_client
        mock_create_client.assert_called_once_with('test-url', 'test-key')

    def test_validate_user_invalid_user(self, mock_supabase_client):
        """Test user validation with invalid user."""
        mock_supabase_client.auth.admin.get_user_by_id.return_value.user = None

        with patch.object(CLIService, '_init_supabase_client', return_value=mock_supabase_client):
            with pytest.raises(ValueError, match="User ID test-user-id not found"):
                CLIService(user_id='test-user-id')

    def test_get_user_config_no_file(self, cli_service):
        """Test get_user_config when file doesn't exist."""
        # Remove config file
        cli_service.config_file.unlink()
        result = cli_service.get_user_config()
        assert result == {}

    def test_get_user_config_existing_file(self, cli_service):
        """Test get_user_config with existing file."""
        result = cli_service.get_user_config()
        assert result == {'userid': 'test-user-id'}

    def test_get_user_id_from_instance(self, cli_service):
        """Test get_user_id returns instance user_id."""
        result = cli_service.get_user_id()
        assert result == 'test-user-id'

    def test_get_user_id_from_config(self, cli_service, temp_config_dir):
        """Test get_user_id from config file when instance user_id not available."""
        # Remove instance user_id to force config file lookup
        delattr(cli_service, 'user_id')

        result = cli_service.get_user_id()
        assert result == 'test-user-id'

    def test_get_user_id_no_config(self, cli_service, temp_config_dir):
        """Test get_user_id when no config exists."""
        # Remove instance user_id and config file
        delattr(cli_service, 'user_id')
        cli_service.config_file.unlink()

        result = cli_service.get_user_id()
        assert result is None

    def test_get_configured_user_id_static_method(self, temp_config_dir):
        """Test static method get_configured_user_id."""
        from configobj import ConfigObj

        # Create config file directly
        config_file = temp_config_dir / 'cfg.ini'
        config = ConfigObj()
        config['user'] = {'userid': 'static-test-user-id'}
        config.filename = str(config_file)
        config.write()

        # Mock Path.home() to return our temp directory
        with patch('pathlib.Path.home', return_value=temp_config_dir):
            result = CLIService.get_configured_user_id()
            assert result == 'static-test-user-id'

    def test_get_configured_user_id_no_config(self):
        """Test static method when no config file exists."""
        with patch('pathlib.Path.home') as mock_home:
            # Use a non-existent directory
            mock_home.return_value = Path('/non/existent/path')
            result = CLIService.get_configured_user_id()
            assert result is None

    def test_get_configured_user_id_empty_config(self, temp_config_dir):
        """Test static method with empty config file."""
        from configobj import ConfigObj

        # Create empty config file
        config_file = temp_config_dir / 'cfg.ini'
        config = ConfigObj()
        config.filename = str(config_file)
        config.write()

        with patch('pathlib.Path.home', return_value=temp_config_dir):
            result = CLIService.get_configured_user_id()
            assert result is None

    def test_set_user_config_new_user(self, cli_service, temp_config_dir):
        """Test setting user config for new user."""
        # Remove existing config
        cli_service.config_file.unlink()

        # Mock validation
        with patch.object(cli_service, '_validate_user'):
            cli_service.set_user_config('new-user-id')

        # Verify config was written
        config = ConfigObj(str(cli_service.config_file))
        assert config['user']['userid'] == 'new-user-id'

    def test_set_user_config_invalid_user(self, cli_service):
        """Test setting user config with invalid user."""
        mock_client = Mock()
        mock_client.auth.admin.get_user_by_id.side_effect = Exception("User not found")

        with patch.object(CLIService, '_init_supabase_client', return_value=mock_client):
            with pytest.raises(ValueError, match="Failed to validate user ID"):
                cli_service.set_user_config('invalid-user-id')

    def test_projects_create_success(self, cli_service):
        """Test successful project creation."""
        cli_service.supabase_client.table.return_value.insert.return_value.execute.return_value.data = [
            {'id': 'new-project-id'}
        ]

        result = cli_service.projects_create('Test Project')
        assert result == 'new-project-id'

        # Verify database call
        cli_service.supabase_client.table.assert_called_with('projects')

    def test_projects_create_duplicate_name(self, cli_service):
        """Test project creation with duplicate name."""
        cli_service.supabase_client.table.return_value.insert.return_value.execute.side_effect = \
            Exception("unique_user_project_name")

        with pytest.raises(ValueError, match="Project 'Test Project' already exists"):
            cli_service.projects_create('Test Project')

    def test_projects_create_database_error(self, cli_service):
        """Test project creation with database error."""
        cli_service.supabase_client.table.return_value.insert.return_value.execute.return_value.data = []

        with pytest.raises(ValueError, match="Failed to create project"):
            cli_service.projects_create('Test Project')

    def test_project_exists_true(self, cli_service):
        """Test project_exists returns True for existing project."""
        cli_service.supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {'id': 'test-project-id'}
        ]

        result = cli_service.project_exists('test-project-id')
        assert result is True

    def test_project_exists_false(self, cli_service):
        """Test project_exists returns False for non-existing project."""
        cli_service.supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []

        result = cli_service.project_exists('non-existing-id')
        assert result is False

    def test_project_exists_exception(self, cli_service):
        """Test project_exists returns False on exception."""
        cli_service.supabase_client.table.side_effect = Exception("Database error")

        result = cli_service.project_exists('test-project-id')
        assert result is False

    def test_projects_list_success(self, cli_service):
        """Test successful projects listing."""
        mock_projects = [
            {'id': 'project-1', 'name': 'Project 1'},
            {'id': 'project-2', 'name': 'Project 2'}
        ]
        cli_service.supabase_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = mock_projects

        result = cli_service.projects_list()
        assert result == mock_projects

    def test_projects_list_database_error(self, cli_service):
        """Test projects listing with database error."""
        cli_service.supabase_client.table.side_effect = Exception("Database error")

        with pytest.raises(ValueError, match="Failed to list projects"):
            cli_service.projects_list()

    def test_project_activate_success(self, cli_service, temp_config_dir):
        """Test successful project activation."""
        # Mock project exists
        with patch.object(cli_service, 'project_exists', return_value=True):
            cli_service.project_activate('test-project-id')

        # Verify config was written
        config = ConfigObj(str(cli_service.project_config_file))
        assert config['active']['project_id'] == 'test-project-id'

    def test_project_activate_not_found(self, cli_service):
        """Test project activation with non-existing project."""
        with patch.object(cli_service, 'project_exists', return_value=False):
            with pytest.raises(ValueError, match="Project test-project-id not found"):
                cli_service.project_activate('test-project-id')

    def test_dataset_activate_success(self, cli_service, temp_config_dir):
        """Test successful dataset activation."""
        cli_service.supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {'id': 'test-dataset-id'}
        ]

        cli_service.dataset_activate('test-dataset-id')

        # Verify config was written
        config = ConfigObj(str(cli_service.project_config_file))
        assert config['active']['dataset_id'] == 'test-dataset-id'

    def test_dataset_activate_not_found(self, cli_service):
        """Test dataset activation with non-existing dataset."""
        cli_service.supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []

        with pytest.raises(ValueError, match="Dataset test-dataset-id not found"):
            cli_service.dataset_activate('test-dataset-id')

    def test_sheet_activate_success(self, cli_service, temp_config_dir):
        """Test successful sheet activation."""
        cli_service.supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {'id': 'test-sheet-id'}
        ]

        cli_service.sheet_activate('test-sheet-id')

        # Verify config was written
        config = ConfigObj(str(cli_service.project_config_file))
        assert config['active']['sheet_id'] == 'test-sheet-id'

    def test_sheet_activate_not_found(self, cli_service):
        """Test sheet activation with non-existing sheet."""
        cli_service.supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []

        with pytest.raises(ValueError, match="Datasheet test-sheet-id not found"):
            cli_service.sheet_activate('test-sheet-id')

    def test_get_active_no_file(self, cli_service):
        """Test get_active when config file doesn't exist."""
        result = cli_service.get_active()
        assert result == {}

    def test_get_active_with_file(self, cli_service, temp_config_dir):
        """Test get_active with existing config file."""
        # Create project config
        config = ConfigObj()
        config['active'] = {
            'project_id': 'test-project',
            'dataset_id': 'test-dataset',
            'sheet_id': 'test-sheet'
        }
        config.filename = str(cli_service.project_config_file)
        config.write()

        result = cli_service.get_active()
        expected = {
            'project_id': 'test-project',
            'dataset_id': 'test-dataset',
            'sheet_id': 'test-sheet'
        }
        assert result == expected

    def test_interactive_project_select_success(self, cli_service):
        """Test successful interactive project selection."""
        mock_projects = [
            {'id': 'project-1', 'name': 'Project 1'},
            {'id': 'project-2', 'name': 'Project 2'}
        ]

        with patch.object(cli_service, 'projects_list', return_value=mock_projects):
            with patch('builtins.input', return_value='1'):
                result = cli_service.interactive_project_select()
                assert result == 'project-1'

    def test_interactive_project_select_no_projects(self, cli_service):
        """Test interactive project selection with no projects."""
        with patch.object(cli_service, 'projects_list', return_value=[]):
            with pytest.raises(ValueError, match="No projects found"):
                cli_service.interactive_project_select()

    def test_interactive_project_select_invalid_choice(self, cli_service):
        """Test interactive project selection with invalid choice."""
        mock_projects = [{'id': 'project-1', 'name': 'Project 1'}]

        with patch.object(cli_service, 'projects_list', return_value=mock_projects):
            with patch('builtins.input', side_effect=['5', '1']):  # Invalid then valid
                result = cli_service.interactive_project_select()
                assert result == 'project-1'

    def test_interactive_project_select_cancelled(self, cli_service):
        """Test interactive project selection when cancelled."""
        mock_projects = [{'id': 'project-1', 'name': 'Project 1'}]

        with patch.object(cli_service, 'projects_list', return_value=mock_projects):
            with patch('builtins.input', return_value=''):  # Empty input
                with pytest.raises(ValueError, match="Project selection cancelled"):
                    cli_service.interactive_project_select()

    def test_interactive_project_select_keyboard_interrupt(self, cli_service):
        """Test interactive project selection with keyboard interrupt."""
        mock_projects = [{'id': 'project-1', 'name': 'Project 1'}]

        with patch.object(cli_service, 'projects_list', return_value=mock_projects):
            with patch('builtins.input', side_effect=KeyboardInterrupt):
                with pytest.raises(ValueError, match="Project selection cancelled"):
                    cli_service.interactive_project_select()


if __name__ == '__main__':
    pytest.main([__file__])