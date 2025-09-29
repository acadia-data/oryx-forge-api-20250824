"""Integration tests for CLIService."""

import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
from configobj import ConfigObj
from typing import Optional

from ..services.cli_service import CLIService
from ..services.utils import init_supabase_client


class TestCLIService:
    """Integration test cases for CLIService."""

    USER_ID = '24d811e2-1801-4208-8030-a86abbda59b8'

    @pytest.fixture(scope="class")
    def supabase_client(self):
        """Get real Supabase client."""
        return init_supabase_client()

    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary directory for config files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def temp_working_dir(self):
        """Create temporary working directory for project configs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def config_patch(self, temp_config_dir):
        """Patch the config_dir to use temp directory."""
        config_dir = temp_config_dir / '.oryxforge'
        config_dir.mkdir(exist_ok=True)
        with patch.object(CLIService, 'config_dir', new=property(lambda self: config_dir)):
            yield config_dir

    @pytest.fixture
    def cli_service(self, config_patch, temp_working_dir):
        """Create CLIService instance for integration testing."""
        # Create config file with user ID
        config_file = config_patch / 'cfg.ini'
        config = ConfigObj()
        config['user'] = {'userid': self.USER_ID}
        config.filename = str(config_file)
        config.write()

        # Create service with temp working directory
        service = CLIService(user_id=self.USER_ID, cwd=str(temp_working_dir))
        return service

    @pytest.fixture
    def test_project_name(self):
        """Generate unique project name for testing."""
        return f"test_project_{int(time.time())}"

    def test_init_with_user_id(self, temp_working_dir):
        """Test initialization with explicit user ID."""
        service = CLIService(user_id=self.USER_ID, cwd=str(temp_working_dir))
        assert service.user_id == self.USER_ID

    def test_init_without_config_raises_error(self, temp_config_dir, temp_working_dir):
        """Test initialization without config raises error."""
        with patch.object(CLIService, 'config_dir', new_callable=lambda: temp_config_dir):
            # Don't create config file - should raise error
            with pytest.raises(ValueError, match="No user ID configured"):
                CLIService(cwd=str(temp_working_dir))

    def test_init_with_invalid_user_id(self, temp_working_dir):
        """Test initialization with invalid user ID."""
        with pytest.raises(ValueError, match="Failed to validate user"):
            CLIService(user_id='00000000-0000-0000-0000-000000000000', cwd=str(temp_working_dir))

    def test_validate_user_success(self, cli_service):
        """Test successful user validation."""
        # Should not raise an exception - user is valid
        assert cli_service.user_id == self.USER_ID

    def test_validate_user_invalid_user(self, temp_working_dir):
        """Test user validation with invalid user."""
        with pytest.raises(ValueError, match="Failed to validate user"):
            CLIService(user_id='invalid-user-id', cwd=str(temp_working_dir))

    def test_get_user_config_no_file(self, cli_service):
        """Test get_user_config when file doesn't exist."""
        # Remove config file
        cli_service.config_file.unlink()
        result = cli_service.get_user_config()
        assert result == {}

    def test_get_user_config_existing_file(self, cli_service):
        """Test get_user_config with existing file."""
        result = cli_service.get_user_config()
        assert result == {'userid': self.USER_ID}

    def test_get_user_id_from_instance(self, cli_service):
        """Test get_user_id returns instance user_id."""
        result = cli_service.get_user_id()
        assert result == self.USER_ID

    def test_get_user_id_from_config(self, cli_service):
        """Test get_user_id from config file when instance user_id not available."""
        # Save and remove instance user_id to force config file lookup
        original_id = cli_service.user_id
        delattr(cli_service, 'user_id')

        try:
            result = cli_service.get_user_id()
            assert result == self.USER_ID
        finally:
            # Restore user_id
            cli_service.user_id = original_id

    def test_get_user_id_no_config(self, cli_service):
        """Test get_user_id when no config exists."""
        # Save original, remove instance user_id and config file
        original_id = cli_service.user_id
        delattr(cli_service, 'user_id')
        cli_service.config_file.unlink()

        try:
            result = cli_service.get_user_id()
            assert result is None
        finally:
            cli_service.user_id = original_id

    def test_get_configured_user_id_static_method(self, temp_config_dir):
        """Test static method get_configured_user_id."""
        # Create config directory structure
        config_dir = temp_config_dir / '.oryxforge'
        config_dir.mkdir(exist_ok=True)
        config_file = config_dir / 'cfg.ini'
        config = ConfigObj()
        config['user'] = {'userid': self.USER_ID}
        config.filename = str(config_file)
        config.write()

        # Mock Path.home() to return our temp directory
        with patch('pathlib.Path.home', return_value=temp_config_dir):
            result = CLIService.get_configured_user_id()
            assert result == self.USER_ID

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

    def test_set_user_config_valid_user(self, cli_service):
        """Test setting user config for valid user."""
        # Remove existing config
        cli_service.config_file.unlink()

        # Set config with valid user ID (same as test user)
        cli_service.set_user_config(self.USER_ID)

        # Verify config was written
        config = ConfigObj(str(cli_service.config_file))
        assert config['user']['userid'] == self.USER_ID

    def test_set_user_config_invalid_user(self, cli_service):
        """Test setting user config with invalid user."""
        with pytest.raises(ValueError, match="Failed to validate user"):
            cli_service.set_user_config('00000000-0000-0000-0000-000000000000')

    def test_projects_create_success(self, cli_service, test_project_name):
        """Test successful project creation."""
        # Create a project
        project_id = cli_service.projects_create(test_project_name)
        assert isinstance(project_id, str)
        assert len(project_id) > 0

        # Verify it exists
        projects = cli_service.projects_list()
        created_project = next((p for p in projects if p['id'] == project_id), None)
        assert created_project is not None
        assert created_project['name'] == test_project_name

        # Clean up
        try:
            cli_service.supabase_client.table("projects").delete().eq("id", project_id).execute()
        except Exception:
            pass

    def test_projects_create_duplicate_name(self, cli_service, test_project_name):
        """Test project creation with duplicate name."""
        # Create first project
        project_id = cli_service.projects_create(test_project_name)

        try:
            # Try to create another with same name
            with pytest.raises(ValueError, match="already exists"):
                cli_service.projects_create(test_project_name)
        finally:
            # Clean up
            try:
                cli_service.supabase_client.table("projects").delete().eq("id", project_id).execute()
            except Exception:
                pass

    def test_projects_create_empty_name(self, cli_service):
        """Test project creation with empty name."""
        # Try to create project with empty name
        with pytest.raises(Exception):  # Should fail validation
            cli_service.projects_create('')

    def test_project_exists_true(self, cli_service, test_project_name):
        """Test project_exists returns True for existing project."""
        # Create a project
        project_id = cli_service.projects_create(test_project_name)

        try:
            # Check that it exists
            result = cli_service.project_exists(project_id)
            assert result is True
        finally:
            # Clean up
            try:
                cli_service.supabase_client.table("projects").delete().eq("id", project_id).execute()
            except Exception:
                pass

    def test_project_exists_false(self, cli_service):
        """Test project_exists returns False for non-existing project."""
        # Use valid UUID that doesn't exist
        result = cli_service.project_exists('00000000-0000-0000-0000-000000000000')
        assert result is False

    def test_project_exists_invalid_uuid(self, cli_service):
        """Test project_exists with invalid UUID format."""
        # Invalid UUID format should return False (caught in exception handler)
        result = cli_service.project_exists('invalid-uuid')
        assert result is False

    def test_projects_list_success(self, cli_service):
        """Test successful projects listing."""
        result = cli_service.projects_list()
        assert isinstance(result, list)
        # All results should have id and name
        for project in result:
            assert 'id' in project
            assert 'name' in project

    def test_projects_list_with_created_project(self, cli_service, test_project_name):
        """Test projects listing includes created project."""
        # Create a project
        project_id = cli_service.projects_create(test_project_name)

        try:
            # List should include the created project
            result = cli_service.projects_list()
            project_ids = [p['id'] for p in result]
            assert project_id in project_ids
        finally:
            # Clean up
            try:
                cli_service.supabase_client.table("projects").delete().eq("id", project_id).execute()
            except Exception:
                pass

    def test_project_activate_success(self, cli_service, test_project_name):
        """Test successful project activation."""
        # Create a project
        project_id = cli_service.projects_create(test_project_name)

        try:
            # Activate the project
            cli_service.project_activate(project_id)

            # Verify config was written
            config = ConfigObj(str(cli_service.project_config_file))
            assert config['active']['project_id'] == project_id
        finally:
            # Clean up
            try:
                cli_service.supabase_client.table("projects").delete().eq("id", project_id).execute()
            except Exception:
                pass

    def test_project_activate_not_found(self, cli_service):
        """Test project activation with non-existing project."""
        with pytest.raises(ValueError, match="Project .* not found"):
            cli_service.project_activate('00000000-0000-0000-0000-000000000000')

    def test_dataset_activate_success(self, cli_service, test_project_name):
        """Test successful dataset activation."""
        # Need to create project and dataset first
        from ..services.project_service import ProjectService

        # Create project
        project_id = cli_service.projects_create(test_project_name)

        try:
            # Create ProjectService to manage datasets
            proj_service = ProjectService(project_id, self.USER_ID)
            dataset_id = proj_service.ds_create(f'dataset_in_{test_project_name}')

            # Activate the dataset
            cli_service.dataset_activate(dataset_id)

            # Verify config was written
            config = ConfigObj(str(cli_service.project_config_file))
            assert config['active']['dataset_id'] == dataset_id
        finally:
            # Clean up
            try:
                cli_service.supabase_client.table("datasets").delete().eq("project_id", project_id).execute()
                cli_service.supabase_client.table("projects").delete().eq("id", project_id).execute()
            except Exception:
                pass

    def test_dataset_activate_not_found(self, cli_service):
        """Test dataset activation with non-existing dataset."""
        with pytest.raises(ValueError, match="Dataset .* not found"):
            cli_service.dataset_activate('00000000-0000-0000-0000-000000000000')

    def test_sheet_activate_success(self, cli_service, test_project_name):
        """Test successful sheet activation."""
        # Need to create project, dataset, and sheet first
        from ..services.project_service import ProjectService

        # Create project
        project_id = cli_service.projects_create(test_project_name)

        try:
            # Create ProjectService to manage datasets and sheets
            proj_service = ProjectService(project_id, self.USER_ID)
            dataset_id = proj_service.ds_create(f'dataset_in_{test_project_name}')
            sheet_id = proj_service.sheet_create(dataset_id, f'sheet_in_{test_project_name}')

            # Activate the sheet
            cli_service.sheet_activate(sheet_id)

            # Verify config was written
            config = ConfigObj(str(cli_service.project_config_file))
            assert config['active']['sheet_id'] == sheet_id
        finally:
            # Clean up
            try:
                cli_service.supabase_client.table("datasheets").delete().eq("dataset_id", dataset_id).execute()
                cli_service.supabase_client.table("datasets").delete().eq("project_id", project_id).execute()
                cli_service.supabase_client.table("projects").delete().eq("id", project_id).execute()
            except Exception:
                pass

    def test_sheet_activate_not_found(self, cli_service):
        """Test sheet activation with non-existing sheet."""
        with pytest.raises(ValueError, match="Datasheet .* not found"):
            cli_service.sheet_activate('00000000-0000-0000-0000-000000000000')

    def test_get_active_no_file(self, cli_service):
        """Test get_active when config file doesn't exist."""
        # Make sure no config file exists
        if cli_service.project_config_file.exists():
            cli_service.project_config_file.unlink()

        result = cli_service.get_active()
        assert result == {}

    def test_get_active_with_file(self, cli_service, test_project_name):
        """Test get_active with existing config file."""
        # Create a project and activate it
        project_id = cli_service.projects_create(test_project_name)

        try:
            cli_service.project_activate(project_id)

            # Get active config
            result = cli_service.get_active()
            assert result['project_id'] == project_id
        finally:
            # Clean up
            try:
                cli_service.supabase_client.table("projects").delete().eq("id", project_id).execute()
            except Exception:
                pass

    def test_interactive_project_select_success(self, cli_service, test_project_name):
        """Test successful interactive project selection."""
        # Create a project
        project_id = cli_service.projects_create(test_project_name)

        try:
            with patch('builtins.input', return_value='1'):
                result = cli_service.interactive_project_select()
                # Should return a valid project ID
                assert isinstance(result, str)
                assert len(result) > 0
        finally:
            # Clean up
            try:
                cli_service.supabase_client.table("projects").delete().eq("id", project_id).execute()
            except Exception:
                pass

    def test_interactive_project_select_no_projects(self, cli_service):
        """Test interactive project selection with no projects."""
        # Check if projects exist
        projects = cli_service.projects_list()
        if len(projects) == 0:
            with pytest.raises(ValueError, match="No projects found"):
                cli_service.interactive_project_select()
        else:
            # Skip test if projects already exist
            pytest.skip("Projects already exist for test user")

    def test_interactive_project_select_invalid_choice(self, cli_service, test_project_name):
        """Test interactive project selection with invalid choice."""
        # Create a project
        project_id = cli_service.projects_create(test_project_name)

        try:
            with patch('builtins.input', side_effect=['999', '1']):  # Invalid then valid
                result = cli_service.interactive_project_select()
                # Should eventually return a valid project ID
                assert isinstance(result, str)
                assert len(result) > 0
        finally:
            # Clean up
            try:
                cli_service.supabase_client.table("projects").delete().eq("id", project_id).execute()
            except Exception:
                pass

    def test_interactive_project_select_cancelled(self, cli_service, test_project_name):
        """Test interactive project selection when cancelled."""
        # Create a project
        project_id = cli_service.projects_create(test_project_name)

        try:
            with patch('builtins.input', return_value=''):  # Empty input
                with pytest.raises(ValueError, match="Project selection cancelled"):
                    cli_service.interactive_project_select()
        finally:
            # Clean up
            try:
                cli_service.supabase_client.table("projects").delete().eq("id", project_id).execute()
            except Exception:
                pass

    def test_interactive_project_select_keyboard_interrupt(self, cli_service, test_project_name):
        """Test interactive project selection with keyboard interrupt."""
        # Create a project
        project_id = cli_service.projects_create(test_project_name)

        try:
            with patch('builtins.input', side_effect=KeyboardInterrupt):
                with pytest.raises(ValueError, match="Project selection cancelled"):
                    cli_service.interactive_project_select()
        finally:
            # Clean up
            try:
                cli_service.supabase_client.table("projects").delete().eq("id", project_id).execute()
            except Exception:
                pass


if __name__ == '__main__':
    pytest.main([__file__])