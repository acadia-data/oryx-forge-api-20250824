"""Integration tests for RepoService."""

import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
import pygit2

from ..services.repo_service import RepoService
from ..services.project_service import ProjectService
from ..services.utils import init_supabase_client


class TestRepoService:
    """Integration test cases for RepoService - no mocks, real GitLab API."""

    USER_ID = '24d811e2-1801-4208-8030-a86abbda59b8'
    TEST_PROJECT_NAME_GIT = "oryx-forge-test-repo"  # Fixed test repo name

    @pytest.fixture(scope="class")
    def supabase_client(self):
        """Get real Supabase client."""
        return init_supabase_client()

    @pytest.fixture(scope="class")
    def test_project_id(self, supabase_client):
        """Find or create test project with name_git field."""
        # Look for existing test project
        response = (
            supabase_client.table("projects")
            .select("*")
            .eq("user_owner", self.USER_ID)
            .eq("name_git", self.TEST_PROJECT_NAME_GIT)
            .execute()
        )

        if response.data:
            return response.data[0]['id']

        # Create test project if not exists
        project_data = {
            "name": "Test Repo Project",
            "name_git": self.TEST_PROJECT_NAME_GIT,
            "user_owner": self.USER_ID
        }
        response = supabase_client.table("projects").insert(project_data).execute()
        return response.data[0]['id']

    @pytest.fixture
    def temp_working_dir(self):
        """Create temporary working directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def repo_service(self, test_project_id, temp_working_dir):
        """Create RepoService instance for integration testing."""
        return RepoService(test_project_id, str(temp_working_dir))

    def test_create_repo_idempotent(self, repo_service):
        """Test repository creation is idempotent - real GitLab API."""
        # First call - may create or return False if exists
        result1 = repo_service.create_repo()
        assert isinstance(result1, bool)

        # Second call - should always return False (already exists)
        result2 = repo_service.create_repo()
        assert result2 is False

        # Verify repo exists on GitLab
        assert repo_service._repo_exists_on_gitlab() is True

    def test_repo_exists_on_gitlab(self, repo_service):
        """Test GitLab repository detection - real API call."""
        # Ensure repo exists first
        repo_service.create_repo()

        # Check detection works
        exists = repo_service._repo_exists_on_gitlab()
        assert exists is True

    def test_repo_exists_locally_false(self, repo_service):
        """Test local repository detection when not cloned."""
        exists = repo_service.repo_exists_locally()
        assert exists is False

    def test_repo_exists_locally_true(self, repo_service):
        """Test local repository detection after cloning."""
        # Ensure GitLab repo exists
        repo_service.create_repo()

        # Clone repository
        repo_path = repo_service.clone()
        assert Path(repo_path).exists()

        # Check local detection
        exists = repo_service.repo_exists_locally()
        assert exists is True

    def test_clone_success(self, repo_service):
        """Test repository cloning - real GitLab clone."""
        # Ensure GitLab repo exists
        repo_service.create_repo()

        # Clone repository
        repo_path = repo_service.clone()

        # Verify clone success
        assert Path(repo_path).exists()
        assert (Path(repo_path) / '.git').exists()

        # Verify it's the correct repository
        repo = pygit2.Repository(repo_path)
        origin = repo.remotes.get("origin")
        assert origin is not None
        assert "oryx-forge/" in origin.url
        assert self.TEST_PROJECT_NAME_GIT in origin.url

    def test_clone_to_custom_path(self, repo_service, temp_working_dir):
        """Test cloning to custom target path."""
        # Ensure GitLab repo exists
        repo_service.create_repo()

        # Clone to specific path
        target_path = temp_working_dir / "custom_clone_location"
        repo_path = repo_service.clone(str(target_path))

        assert Path(repo_path) == target_path
        assert (target_path / '.git').exists()

    def test_ensure_repo_clone_when_missing(self, repo_service):
        """Test ensure_repo clones when repository missing locally."""
        # Ensure GitLab repo exists
        repo_service.create_repo()

        # Repository should not exist locally initially
        assert repo_service.repo_exists_locally() is False

        # ensure_repo should clone
        repo_path = repo_service.ensure_repo()

        # Verify clone happened
        assert Path(repo_path).exists()
        assert repo_service.repo_exists_locally() is True

    def test_ensure_repo_pull_when_exists(self, repo_service):
        """Test ensure_repo pulls when repository exists locally."""
        # Setup: ensure GitLab repo exists and is cloned
        repo_service.create_repo()
        repo_service.clone()

        # Repository should exist locally
        assert repo_service.repo_exists_locally() is True

        # ensure_repo should pull (not clone again)
        repo_path = repo_service.ensure_repo()

        # Verify still exists and is up to date
        assert Path(repo_path).exists()
        assert repo_service.repo_exists_locally() is True

    def test_pull_success(self, repo_service):
        """Test pulling latest changes - real git operation."""
        # Setup: ensure repo exists and is cloned
        repo_service.create_repo()
        repo_service.clone()

        # Pull should succeed (even if no new changes)
        repo_service.pull()

        # Verify repository is still valid
        assert repo_service.repo_exists_locally() is True

    def test_push_success(self, repo_service):
        """Test pushing changes - real git operation."""
        # Setup: ensure repo exists and is cloned
        repo_service.create_repo()
        repo_path = repo_service.clone()

        # Make a change
        test_file = Path(repo_path) / "integration_test.txt"
        test_content = f"Integration test at {time.time()}"
        test_file.write_text(test_content)

        # Push changes
        commit_hash = repo_service.push("Integration test commit")

        # Verify push succeeded
        assert isinstance(commit_hash, str)
        assert len(commit_hash) > 0

        # Verify file was actually pushed (check repo state)
        repo = pygit2.Repository(repo_path)
        head_commit = repo.head.target
        assert str(head_commit) == commit_hash

    def test_clone_nonexistent_repo(self, temp_working_dir):
        """Test cloning non-existent repository fails gracefully."""
        # Create service with non-existent project
        fake_service = RepoService("00000000-0000-0000-0000-000000000000", str(temp_working_dir))

        with pytest.raises(ValueError, match="Project .* not found"):
            fake_service.clone()

    def test_pull_no_local_repo(self, repo_service):
        """Test pulling when no local repository exists."""
        # Ensure no local repo
        assert repo_service.repo_exists_locally() is False

        with pytest.raises(ValueError, match="No local repository"):
            repo_service.pull()

    def test_push_no_local_repo(self, repo_service):
        """Test pushing when no local repository exists."""
        # Ensure no local repo
        assert repo_service.repo_exists_locally() is False

        with pytest.raises(ValueError, match="No local repository"):
            repo_service.push("test commit")

    def test_complete_workflow(self, repo_service):
        """Test complete workflow: create → clone → modify → push → pull."""
        # Step 1: Create repository (idempotent)
        created = repo_service.create_repo()
        assert isinstance(created, bool)

        # Step 2: Ensure repository locally (should clone)
        repo_path = repo_service.ensure_repo()
        assert Path(repo_path).exists()

        # Step 3: Make changes
        test_file = Path(repo_path) / f"workflow_test_{int(time.time())}.txt"
        test_file.write_text("Complete workflow integration test")

        # Step 4: Push changes
        commit_hash = repo_service.push("Complete workflow test")
        assert len(commit_hash) > 0

        # Step 5: Pull to verify everything synced
        repo_service.pull()

        # Verify final state
        assert repo_service.repo_exists_locally() is True
        assert test_file.exists()

    def test_project_service_integration(self, test_project_id, temp_working_dir):
        """Test ProjectService using RepoService for project_init."""
        # Create ProjectService with temp directory
        with patch('pathlib.Path.cwd', return_value=temp_working_dir):
            project_service = ProjectService(test_project_id, self.USER_ID)

            # Call project_init (should use RepoService internally)
            project_service.project_init()

            # Verify repository was set up
            assert (temp_working_dir / '.git').exists()
            assert (temp_working_dir / '.gitignore').exists()

            # Verify it's the correct oryx-forge repository
            repo = pygit2.Repository(str(temp_working_dir))
            origin = repo.remotes.get("origin")
            assert origin is not None
            assert "oryx-forge/" in origin.url


    def test_invalid_project_id(self, temp_working_dir):
        """Test error handling with invalid project ID."""
        repo_service = RepoService("00000000-0000-0000-0000-000000000000", str(temp_working_dir))

        with pytest.raises(ValueError, match="Project .* not found"):
            repo_service.create_repo()


if __name__ == '__main__':
    pytest.main([__file__])