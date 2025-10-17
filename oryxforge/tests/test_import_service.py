"""Integration tests for ImportService."""

import pytest
import tempfile
import pandas as pd
from pathlib import Path

from ..services.import_service import ImportService
from ..services.utils import init_supabase_client
from ..services.project_service import ProjectService


class TestImportService:
    """Integration test cases for ImportService."""

    USER_ID = '24d811e2-1801-4208-8030-a86abbda59b8'
    PROJECT_ID = 'fd0b6b50-ed50-49db-a3ce-6c7295fb85a2'

    @pytest.fixture(scope="class")
    def supabase_client(self):
        """Get real Supabase client."""
        return init_supabase_client()

    @pytest.fixture
    def temp_working_dir(self):
        """Create temporary working directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def project_context_setup(self, temp_working_dir):
        """Set up ProjectContext for tests that create ImportService."""
        from ..services.env_config import ProjectContext

        ProjectContext.set(
            user_id=self.USER_ID,
            project_id=self.PROJECT_ID,
            working_dir=temp_working_dir
        )

        yield temp_working_dir

        ProjectContext.clear()

    @pytest.fixture
    def sample_csv_file(self, temp_working_dir):
        """Create a sample CSV file for testing."""
        df = pd.DataFrame({
            'col1': [1, 2, 3],
            'col2': ['a', 'b', 'c']
        })
        csv_path = Path(temp_working_dir) / 'test.csv'
        df.to_csv(csv_path, index=False)
        return str(csv_path)

    @pytest.fixture
    def data_source_local(self, supabase_client, sample_csv_file):
        """Create a data_sources entry with local:// URI."""
        file_uri = f"local://{Path(sample_csv_file).resolve()}"

        response = supabase_client.table("data_sources").insert({
            "uri": file_uri,
            "name": "test.csv",
            "type": "csv",
            "user_owner": self.USER_ID,
            "project_id": self.PROJECT_ID,
            "status": {
                "flag": "pending",
                "msg": "File registered, awaiting processing"
            }
        }).execute()

        file_id = response.data[0]['id']
        yield file_id

        # Cleanup
        supabase_client.table("data_sources").delete().eq("id", file_id).execute()

    @pytest.fixture
    def data_source_supabase(self, supabase_client):
        """Create a data_sources entry with supabase:// URI."""
        response = supabase_client.table("data_sources").insert({
            "uri": "supabase://test-bucket/test-file.csv",
            "name": "test-file.csv",
            "type": "csv",
            "user_owner": self.USER_ID,
            "project_id": self.PROJECT_ID,
            "status": {
                "flag": "pending",
                "msg": "File registered, awaiting processing"
            }
        }).execute()

        file_id = response.data[0]['id']
        yield file_id

        # Cleanup
        supabase_client.table("data_sources").delete().eq("id", file_id).execute()

    def test_init_success(self, data_source_local, supabase_client, project_context_setup):
        """Test successful initialization with local file."""
        service = ImportService(file_id=data_source_local)

        assert service.file_id == data_source_local
        assert service.file is not None
        assert service.file['name'] == 'test.csv'
        assert service.project_service is not None

    def test_init_invalid_file_id(self, project_context_setup):
        """Test initialization with invalid file_id raises error."""
        # Use a valid UUID format that doesn't exist
        with pytest.raises(ValueError, match="No file found with file_id"):
            ImportService(file_id="00000000-0000-0000-0000-000000000000")

    def test_filepath_local(self, data_source_local, project_context_setup):
        """Test filepath() method with local:// URI."""
        service = ImportService(file_id=data_source_local)
        file_path = service.filepath()

        assert isinstance(file_path, Path)
        assert file_path.exists()

    def test_filepath_supabase(self, data_source_supabase, project_context_setup):
        """Test filepath() method with supabase:// URI."""
        service = ImportService(file_id=data_source_supabase)
        file_path = service.filepath()

        assert isinstance(file_path, Path)
        # Compare parts to avoid path separator issues on Windows
        assert file_path.parts == ("data", ".import", "test-file.csv")

    def test_filepath_unsupported_uri(self, supabase_client, project_context_setup):
        """Test filepath() with unsupported URI format."""
        response = supabase_client.table("data_sources").insert({
            "uri": "http://example.com/file.csv",
            "name": "file.csv",
            "type": "csv",
            "user_owner": self.USER_ID,
            "project_id": self.PROJECT_ID,
            "status": {"flag": "pending", "msg": "Test"}
        }).execute()

        file_id = response.data[0]['id']

        try:
            service = ImportService(file_id=file_id)
            with pytest.raises(ValueError, match="Unsupported URI format"):
                service.filepath()
        finally:
            # Cleanup
            supabase_client.table("data_sources").delete().eq("id", file_id).execute()

    def test_exists_local_true(self, data_source_local, project_context_setup):
        """Test exists_local() returns True for existing local file."""
        service = ImportService(file_id=data_source_local)
        assert service.exists_local() is True

    def test_exists_local_false(self, supabase_client, project_context_setup):
        """Test exists_local() returns False for non-existent file."""
        response = supabase_client.table("data_sources").insert({
            "uri": "local:///nonexistent/file.csv",
            "name": "file.csv",
            "type": "csv",
            "user_owner": self.USER_ID,
            "project_id": self.PROJECT_ID,
            "status": {"flag": "pending", "msg": "Test"}
        }).execute()

        file_id = response.data[0]['id']

        try:
            service = ImportService(file_id=file_id)
            assert service.exists_local() is False
        finally:
            # Cleanup
            supabase_client.table("data_sources").delete().eq("id", file_id).execute()

    def test_download_skips_local(self, data_source_local, project_context_setup):
        """Test download() skips files with local:// URI."""
        service = ImportService(file_id=data_source_local)
        # Should not raise any error
        service.download()

    def test_render_prompt(self, data_source_local, project_context_setup):
        """Test _render_prompt() method uses Jinja2."""
        service = ImportService(file_id=data_source_local)

        prompt = service._render_prompt(
            file_path="/path/to/file.csv",
            dataset="Sources",
            sheet="TestSheet"
        )

        assert "/path/to/file.csv" in prompt
        assert 'dataset="Sources"' in prompt
        assert 'sheet="TestSheet"' in prompt

    def test_idempotent_data_source_creation(self, supabase_client, sample_csv_file):
        """Test that creating the same data_source twice with upsert returns same ID."""
        file_uri = f"local://{Path(sample_csv_file).resolve()}"

        # First insert using upsert
        response1 = supabase_client.table("data_sources").upsert({
            "uri": file_uri,
            "name": "test_idempotent.csv",
            "type": "csv",
            "user_owner": self.USER_ID,
            "project_id": self.PROJECT_ID,
            "status": {
                "flag": "pending",
                "msg": "File registered, awaiting processing"
            }
        },
        on_conflict="name,project_id,user_owner").execute()

        file_id_1 = response1.data[0]['id']

        # Second insert with same name - should return same ID (via update)
        response2 = supabase_client.table("data_sources").upsert({
            "uri": file_uri,
            "name": "test_idempotent.csv",
            "type": "csv",
            "user_owner": self.USER_ID,
            "project_id": self.PROJECT_ID,
            "status": {
                "flag": "pending",
                "msg": "File registered, awaiting processing"
            }
        },
        on_conflict="name,project_id,user_owner").execute()

        file_id_2 = response2.data[0]['id']

        try:
            # Should return same ID
            assert file_id_1 == file_id_2, "Upsert should return same ID on retry"
        finally:
            # Cleanup
            supabase_client.table("data_sources").delete().eq("id", file_id_1).execute()

    def test_idempotent_sheet_creation(self, supabase_client, temp_working_dir):
        """Test that creating the same sheet twice with upsert returns same ID."""
        from ..services.env_config import ProjectContext

        # Set up project context (disables auto-mounting)
        ProjectContext.set(
            user_id=self.USER_ID,
            project_id=self.PROJECT_ID,
            working_dir=temp_working_dir
        )

        try:
            # Get Sources dataset
            project_service = ProjectService(working_dir=temp_working_dir)

            sources_dataset = project_service.ds_get(name="Sources")
            dataset_id = sources_dataset['id']

            # First create
            sheet_data_1 = project_service.sheet_create(
                dataset_id=dataset_id,
                name="test_idempotent_sheet"
            )

            # Second create with same name - should return same ID
            sheet_data_2 = project_service.sheet_create(
                dataset_id=dataset_id,
                name="test_idempotent_sheet"
            )

            try:
                # Should return same ID and data
                assert sheet_data_1['id'] == sheet_data_2['id'], "sheet_create should return same ID on retry"
                assert sheet_data_1['name'] == sheet_data_2['name'], "sheet_create should return same name on retry"
                assert sheet_data_1['name_python'] == sheet_data_2['name_python'], "sheet_create should return same name_python on retry"
            finally:
                # Cleanup
                supabase_client.table("datasheets").delete().eq("id", sheet_data_1['id']).execute()
        finally:
            # Cleanup context
            ProjectContext.clear()


if __name__ == '__main__':
    pytest.main([__file__])
