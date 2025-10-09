"""Tests for IAM service (CredentialsManager)."""

import pytest
import tempfile
from pathlib import Path
from configobj import ConfigObj

from ..services.iam import CredentialsManager


class TestCredentialsManager:
    """Test cases for CredentialsManager."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for config files."""
        with tempfile.TemporaryDirectory() as temp_path:
            yield temp_path

    @pytest.fixture
    def creds_manager(self, temp_dir):
        """Create CredentialsManager instance for testing."""
        return CredentialsManager(working_dir=temp_dir)

    def test_init_with_working_dir(self, temp_dir):
        """Test initialization with explicit working directory."""
        manager = CredentialsManager(working_dir=temp_dir)
        assert manager.working_dir == Path(temp_dir)

    def test_init_without_working_dir(self):
        """Test initialization without working directory (uses cwd)."""
        manager = CredentialsManager()
        assert manager.working_dir == Path.cwd()

    def test_config_file_property(self, creds_manager, temp_dir):
        """Test config_file property returns correct path."""
        expected_path = Path(temp_dir) / '.oryxforge.cfg'
        assert creds_manager.config_file == expected_path

    def test_set_profile_creates_file(self, creds_manager):
        """Test set_profile creates configuration file."""
        user_id = "test-user-123"
        project_id = "test-project-456"

        creds_manager.set_profile(user_id, project_id)

        assert creds_manager.config_file.exists()

    def test_set_profile_stores_values(self, creds_manager):
        """Test set_profile stores user_id and project_id correctly."""
        user_id = "test-user-123"
        project_id = "test-project-456"

        creds_manager.set_profile(user_id, project_id)

        # Verify config file contents
        config = ConfigObj(str(creds_manager.config_file))
        assert config['profile']['user_id'] == user_id
        assert config['profile']['project_id'] == project_id

    def test_set_profile_updates_existing(self, creds_manager):
        """Test set_profile updates existing configuration."""
        # Set initial profile
        creds_manager.set_profile("user1", "project1")

        # Update profile
        creds_manager.set_profile("user2", "project2")

        # Verify updated values
        config = ConfigObj(str(creds_manager.config_file))
        assert config['profile']['user_id'] == "user2"
        assert config['profile']['project_id'] == "project2"

    def test_get_profile_success(self, creds_manager):
        """Test get_profile returns correct values."""
        user_id = "test-user-123"
        project_id = "test-project-456"

        creds_manager.set_profile(user_id, project_id)
        profile = creds_manager.get_profile()

        assert profile['user_id'] == user_id
        assert profile['project_id'] == project_id

    def test_get_profile_no_config_file(self, creds_manager):
        """Test get_profile raises error when config file doesn't exist."""
        with pytest.raises(ValueError, match="No profile configured"):
            creds_manager.get_profile()

    def test_get_profile_missing_user_id(self, creds_manager):
        """Test get_profile raises error when user_id is missing."""
        # Create config with only project_id
        config = ConfigObj()
        config['profile'] = {'project_id': 'test-project'}
        config.filename = str(creds_manager.config_file)
        config.write()

        with pytest.raises(ValueError, match="Incomplete profile configuration"):
            creds_manager.get_profile()

    def test_get_profile_missing_project_id(self, creds_manager):
        """Test get_profile raises error when project_id is missing."""
        # Create config with only user_id
        config = ConfigObj()
        config['profile'] = {'user_id': 'test-user'}
        config.filename = str(creds_manager.config_file)
        config.write()

        with pytest.raises(ValueError, match="Incomplete profile configuration"):
            creds_manager.get_profile()

    def test_get_profile_empty_profile_section(self, creds_manager):
        """Test get_profile raises error when profile section is empty."""
        # Create config with empty profile section
        config = ConfigObj()
        config['profile'] = {}
        config.filename = str(creds_manager.config_file)
        config.write()

        with pytest.raises(ValueError, match="Incomplete profile configuration"):
            creds_manager.get_profile()

    def test_clear_profile_success(self, creds_manager):
        """Test clear_profile removes profile section."""
        # Set profile first
        creds_manager.set_profile("user1", "project1")

        # Clear profile
        creds_manager.clear_profile()

        # Verify profile section is removed
        config = ConfigObj(str(creds_manager.config_file))
        assert 'profile' not in config

    def test_clear_profile_no_config_file(self, creds_manager):
        """Test clear_profile handles missing config file gracefully."""
        # Should not raise an error
        creds_manager.clear_profile()

    def test_clear_profile_no_profile_section(self, creds_manager):
        """Test clear_profile handles missing profile section gracefully."""
        # Create config without profile section
        config = ConfigObj()
        config['other'] = {'key': 'value'}
        config.filename = str(creds_manager.config_file)
        config.write()

        # Should not raise an error
        creds_manager.clear_profile()

        # Verify other section remains
        config = ConfigObj(str(creds_manager.config_file))
        assert 'other' in config

    def test_profile_workflow(self, creds_manager):
        """Test complete workflow: set, get, update, clear."""
        # Set profile
        creds_manager.set_profile("user1", "project1")
        profile = creds_manager.get_profile()
        assert profile['user_id'] == "user1"
        assert profile['project_id'] == "project1"

        # Update profile
        creds_manager.set_profile("user2", "project2")
        profile = creds_manager.get_profile()
        assert profile['user_id'] == "user2"
        assert profile['project_id'] == "project2"

        # Clear profile
        creds_manager.clear_profile()
        with pytest.raises(ValueError):
            creds_manager.get_profile()


if __name__ == '__main__':
    pytest.main([__file__])
