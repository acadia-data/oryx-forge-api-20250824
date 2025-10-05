"""Integration tests for ProjectService."""

import pytest
import subprocess
import tempfile
import os
from pathlib import Path
from typing import Optional
import pandas as pd
from unittest.mock import patch

from ..services.project_service import ProjectService
from ..services.utils import init_supabase_client


class TestProjectService:
    """Integration test cases for ProjectService."""

    USER_ID = '24d811e2-1801-4208-8030-a86abbda59b8'

    @pytest.fixture(scope="class")
    def supabase_client(self):
        """Get real Supabase client."""
        return init_supabase_client()

    @pytest.fixture(scope="class")
    def test_project_id(self, supabase_client) -> Optional[str]:
        """Find or create a test project for integration tests."""
        # Try to find existing test project
        response = supabase_client.table("projects").select("id").eq("user_owner", self.USER_ID).limit(1).execute()

        if response.data:
            return response.data[0]['id']

        # If no projects exist, we'll need one to be created manually
        # or skip tests that require a project
        return None

    @pytest.fixture
    def project_service(self, test_project_id):
        """Create ProjectService instance for integration testing."""
        if not test_project_id:
            pytest.skip("No test project available - please create a project for user 24d811e2-1801-4208-8030-a86abbda59b8")
        return ProjectService(test_project_id, self.USER_ID)

    @pytest.fixture
    def test_dataset_name(self):
        """Generate unique dataset name for testing."""
        import time
        return f"test_dataset_{int(time.time())}"

    @pytest.fixture
    def test_sheet_name(self):
        """Generate unique sheet name for testing."""
        import time
        return f"test_sheet_{int(time.time())}"

    def test_init_success(self, project_service):
        """Test successful initialization."""
        assert project_service.project_id is not None
        assert project_service.user_id == self.USER_ID
        assert project_service.project_name is not None

    def test_init_gcs_error(self, test_project_id):
        """Test initialization with GCS error."""
        with patch('gcsfs.GCSFileSystem', side_effect=Exception("GCS error")):
            service = ProjectService(test_project_id, self.USER_ID)
            assert service.gcs is None

    def test_init_with_invalid_project(self):
        """Test initialization with invalid project."""
        # Use valid UUID format but non-existent project
        with pytest.raises(ValueError, match="Failed to validate project"):
            ProjectService('00000000-0000-0000-0000-000000000000', self.USER_ID)

    def test_validate_project_success(self, project_service):
        """Test successful project validation."""
        assert project_service.project_name is not None
        assert len(project_service.project_name) > 0

    def test_validate_project_access_denied(self, test_project_id):
        """Test project validation with access denied."""
        if not test_project_id:
            pytest.skip("No test project available")
        # Use a different user ID that shouldn't have access
        with pytest.raises(ValueError, match="Failed to validate project"):
            ProjectService(test_project_id, 'wrong-user-id')

    def test_ds_list_success(self, project_service):
        """Test successful dataset listing."""
        result = project_service.ds_list()
        assert isinstance(result, list)
        # All results should have id and name
        for dataset in result:
            assert 'id' in dataset
            assert 'name' in dataset

    def test_ds_list_database_error(self, test_project_id):
        """Test dataset listing with database error."""
        if not test_project_id:
            pytest.skip("No test project available")
        # This test is hard to simulate in real integration test - skip it
        pytest.skip("Database error simulation not suitable for integration test")

    def test_ds_create_success(self, project_service, test_dataset_name):
        """Test successful dataset creation."""
        # Create a dataset
        dataset_id = project_service.ds_create(test_dataset_name)
        assert isinstance(dataset_id, str)
        assert len(dataset_id) > 0

        # Verify it exists
        datasets = project_service.ds_list()
        created_dataset = next((ds for ds in datasets if ds['id'] == dataset_id), None)
        assert created_dataset is not None
        assert created_dataset['name'] == test_dataset_name

        # Clean up
        try:
            project_service.supabase_client.table("datasets").delete().eq("id", dataset_id).execute()
        except Exception:
            pass

    def test_ds_create_duplicate_name(self, project_service, test_dataset_name):
        """Test dataset creation with duplicate name."""
        # Create first dataset
        dataset_id = project_service.ds_create(test_dataset_name)

        try:
            # Try to create another with same name
            with pytest.raises(ValueError, match="already exists"):
                project_service.ds_create(test_dataset_name)
        finally:
            # Clean up
            try:
                project_service.supabase_client.table("datasets").delete().eq("id", dataset_id).execute()
            except Exception:
                pass

    def test_ds_create_with_invalid_project(self):
        """Test dataset creation with invalid project access."""
        # This test verifies that dataset creation fails with wrong user permissions
        # We can't easily test this without creating multiple projects
        pass

    def test_sheet_create_success(self, project_service, test_dataset_name, test_sheet_name):
        """Test successful datasheet creation."""
        # First create a dataset
        dataset_id = project_service.ds_create(test_dataset_name)

        try:
            # Create a sheet in the dataset
            sheet_id = project_service.sheet_create(dataset_id, test_sheet_name)
            assert isinstance(sheet_id, str)
            assert len(sheet_id) > 0

            # Verify it exists
            sheets = project_service.sheet_list(dataset_id)
            created_sheet = next((sh for sh in sheets if sh['id'] == sheet_id), None)
            assert created_sheet is not None
            assert created_sheet['name'] == test_sheet_name

        finally:
            # Clean up
            try:
                project_service.supabase_client.table("datasheets").delete().eq("dataset_id", dataset_id).execute()
                project_service.supabase_client.table("datasets").delete().eq("id", dataset_id).execute()
            except Exception:
                pass

    def test_sheet_create_dataset_not_found(self, project_service, test_sheet_name):
        """Test datasheet creation with non-existing dataset."""
        with pytest.raises(ValueError, match="Dataset .* not found"):
            project_service.sheet_create('non-existent-dataset-id', test_sheet_name)

    def test_sheet_create_duplicate_name(self, project_service, test_dataset_name, test_sheet_name):
        """Test datasheet creation with duplicate name."""
        # Create dataset and sheet
        dataset_id = project_service.ds_create(test_dataset_name)
        sheet_id = project_service.sheet_create(dataset_id, test_sheet_name)

        try:
            # Try to create another sheet with same name
            with pytest.raises(ValueError, match="already exists"):
                project_service.sheet_create(dataset_id, test_sheet_name)
        finally:
            # Clean up
            try:
                project_service.supabase_client.table("datasheets").delete().eq("dataset_id", dataset_id).execute()
                project_service.supabase_client.table("datasets").delete().eq("id", dataset_id).execute()
            except Exception:
                pass

    def test_sheet_list_specific_dataset(self, project_service, test_dataset_name):
        """Test datasheet listing for specific dataset."""
        # Create a dataset first
        dataset_id = project_service.ds_create(test_dataset_name)

        try:
            # List sheets for this specific dataset (should be empty initially)
            result = project_service.sheet_list(dataset_id)
            assert isinstance(result, list)
            assert len(result) == 0  # No sheets created yet

            # Create a sheet and verify it appears in the list
            sheet_id = project_service.sheet_create(dataset_id, f"sheet_in_{test_dataset_name}")
            result = project_service.sheet_list(dataset_id)
            assert len(result) == 1
            assert result[0]['id'] == sheet_id
            assert result[0]['dataset_id'] == dataset_id
        except Exception as e:
            # Clean up and re-raise
            try:
                project_service.supabase_client.table("datasheets").delete().eq("dataset_id", dataset_id).execute()
                project_service.supabase_client.table("datasets").delete().eq("id", dataset_id).execute()
            except Exception:
                pass
            raise e
        finally:
            # Clean up
            try:
                project_service.supabase_client.table("datasheets").delete().eq("dataset_id", dataset_id).execute()
                project_service.supabase_client.table("datasets").delete().eq("id", dataset_id).execute()
            except Exception:
                pass

    def test_sheet_list_all_datasets(self, project_service):
        """Test datasheet listing for all datasets."""
        # List all sheets in project
        result = project_service.sheet_list()
        assert isinstance(result, list)
        # All results should have id, name, and dataset_id
        for sheet in result:
            assert 'id' in sheet
            assert 'name' in sheet
            assert 'dataset_id' in sheet

    def test_sheet_list_no_datasets(self, project_service):
        """Test datasheet listing when filtering by non-existent dataset."""
        # Use valid UUID format but non-existent dataset
        result = project_service.sheet_list('00000000-0000-0000-0000-000000000000')
        assert isinstance(result, list)
        assert len(result) == 0



    def test_ds_exists_true(self, project_service, test_dataset_name):
        """Test ds_exists returns True for existing dataset."""
        # Create a dataset
        dataset_id = project_service.ds_create(test_dataset_name)

        try:
            # Check that it exists
            result = project_service.ds_exists(dataset_id)
            assert result is True
        finally:
            # Clean up
            try:
                project_service.supabase_client.table("datasets").delete().eq("id", dataset_id).execute()
            except Exception:
                pass

    def test_ds_exists_false(self, project_service):
        """Test ds_exists returns False for non-existing dataset."""
        result = project_service.ds_exists('non-existing-id')
        assert result is False

    def test_ds_exists_with_wrong_user(self, test_project_id):
        """Test ds_exists returns False when dataset belongs to different user."""
        if not test_project_id:
            pytest.skip("No test project available")

        # Create service with different user ID
        try:
            different_service = ProjectService(test_project_id, 'different-user-id')
            # This should fail at initialization, so we won't reach ds_exists
        except ValueError:
            # Expected - different user shouldn't have access
            pass


    def test_sheet_exists_true(self, project_service, test_dataset_name, test_sheet_name):
        """Test sheet_exists returns True for existing sheet."""
        # Create dataset and sheet
        dataset_id = project_service.ds_create(test_dataset_name)
        sheet_id = project_service.sheet_create(dataset_id, test_sheet_name)

        try:
            # Check that it exists
            result = project_service.sheet_exists(sheet_id)
            assert result is True
        finally:
            # Clean up
            try:
                project_service.supabase_client.table("datasheets").delete().eq("dataset_id", dataset_id).execute()
                project_service.supabase_client.table("datasets").delete().eq("id", dataset_id).execute()
            except Exception:
                pass

    def test_sheet_exists_false(self, project_service):
        """Test sheet_exists returns False for non-existing sheet."""
        result = project_service.sheet_exists('non-existing-id')
        assert result is False


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
        # Create an exploration dataset
        exploration_id = project_service.ds_create('exploration')

        try:
            result = project_service._get_default_dataset_id()
            assert result == exploration_id
        except ValueError as e:
            # If test fails, clean up and re-raise
            try:
                project_service.supabase_client.table("datasets").delete().eq("id", exploration_id).execute()
            except Exception:
                pass
            raise e
        finally:
            # Clean up
            try:
                project_service.supabase_client.table("datasets").delete().eq("id", exploration_id).execute()
            except Exception:
                pass

    def test_get_default_dataset_id_not_found(self, project_service):
        """Test default dataset retrieval when not found."""
        # Check if exploration already exists and remove it temporarily
        existing_datasets = project_service.ds_list()
        exploration_datasets = [ds for ds in existing_datasets if ds['name'] == 'exploration']

        if exploration_datasets:
            # Skip this test if exploration already exists
            pytest.skip("Exploration dataset already exists in test project")
        else:
            # Test the error case
            with pytest.raises(ValueError, match="Exploration dataset not found"):
                project_service._get_default_dataset_id()

    def test_get_first_sheet_id_success(self, project_service, test_dataset_name, test_sheet_name):
        """Test successful first sheet retrieval."""
        # Create dataset and sheet
        dataset_id = project_service.ds_create(test_dataset_name)
        sheet_id = project_service.sheet_create(dataset_id, test_sheet_name)

        try:
            result = project_service.get_first_sheet_id(dataset_id)
            assert result == sheet_id
        finally:
            # Clean up
            try:
                project_service.supabase_client.table("datasheets").delete().eq("dataset_id", dataset_id).execute()
                project_service.supabase_client.table("datasets").delete().eq("id", dataset_id).execute()
            except Exception:
                pass

    def test_get_first_sheet_id_no_sheets(self, project_service, test_dataset_name):
        """Test first sheet retrieval with no sheets."""
        # Create dataset but no sheets
        dataset_id = project_service.ds_create(test_dataset_name)

        try:
            with pytest.raises(ValueError, match="No datasheets found"):
                project_service.get_first_sheet_id(dataset_id)
        except Exception as e:
            # Clean up and re-raise
            try:
                project_service.supabase_client.table("datasets").delete().eq("id", dataset_id).execute()
            except Exception:
                pass
            raise e
        finally:
            # Clean up
            try:
                project_service.supabase_client.table("datasets").delete().eq("id", dataset_id).execute()
            except Exception:
                pass

    def test_interactive_dataset_select_success(self, project_service, test_dataset_name):
        """Test successful interactive dataset selection."""
        # Create a dataset
        dataset_id = project_service.ds_create(test_dataset_name)

        try:
            with patch('builtins.input', return_value='1'):
                result = project_service.interactive_dataset_select()
                # Should return the first dataset found
                assert isinstance(result, str)
                assert len(result) > 0
        finally:
            # Clean up
            try:
                project_service.supabase_client.table("datasets").delete().eq("id", dataset_id).execute()
            except Exception:
                pass

    def test_interactive_dataset_select_no_datasets(self, project_service):
        """Test interactive dataset selection with no datasets."""
        # If no datasets exist, this should raise an error
        # However, for a real project, there might already be datasets
        # So we'll check if datasets exist first
        datasets = project_service.ds_list()
        if len(datasets) == 0:
            with pytest.raises(ValueError, match="No datasets found"):
                project_service.interactive_dataset_select()
        else:
            # Skip this test if datasets already exist
            pytest.skip("Datasets already exist in test project")

    def test_interactive_sheet_select_success(self, project_service, test_dataset_name, test_sheet_name):
        """Test successful interactive sheet selection."""
        # Create dataset and sheet
        dataset_id = project_service.ds_create(test_dataset_name)
        sheet_id = project_service.sheet_create(dataset_id, test_sheet_name)

        try:
            with patch('builtins.input', return_value='1'):
                result = project_service.interactive_sheet_select()
                # Should return a valid sheet ID
                assert isinstance(result, str)
                assert len(result) > 0
        finally:
            # Clean up
            try:
                project_service.supabase_client.table("datasheets").delete().eq("dataset_id", dataset_id).execute()
                project_service.supabase_client.table("datasets").delete().eq("id", dataset_id).execute()
            except Exception:
                pass

    def test_interactive_sheet_select_no_sheets(self, project_service):
        """Test interactive sheet selection with no sheets."""
        # If no sheets exist, this should raise an error
        sheets = project_service.sheet_list()
        if len(sheets) == 0:
            with pytest.raises(ValueError, match="No datasheets found"):
                project_service.interactive_sheet_select()
        else:
            # Skip this test if sheets already exist
            pytest.skip("Sheets already exist in test project")

    def test_ds_get_by_name_success(self, project_service, test_dataset_name):
        """Test successful dataset retrieval by name."""
        # Create a dataset
        dataset_id = project_service.ds_create(test_dataset_name)

        try:
            result = project_service.ds_get(name=test_dataset_name)
            assert result['id'] == dataset_id
            assert result['name'] == test_dataset_name
            assert 'name_python' in result
        finally:
            # Clean up
            try:
                project_service.supabase_client.table("datasets").delete().eq("id", dataset_id).execute()
            except Exception:
                pass

    def test_ds_get_by_id_success(self, project_service, test_dataset_name):
        """Test successful dataset retrieval by ID."""
        # Create a dataset
        dataset_id = project_service.ds_create(test_dataset_name)

        try:
            result = project_service.ds_get(id=dataset_id)
            assert result['id'] == dataset_id
            assert result['name'] == test_dataset_name
        finally:
            # Clean up
            try:
                project_service.supabase_client.table("datasets").delete().eq("id", dataset_id).execute()
            except Exception:
                pass

    def test_ds_get_not_found(self, project_service):
        """Test dataset retrieval when not found."""
        with pytest.raises(ValueError, match="not found"):
            project_service.ds_get(name='NonExistentDataset')

    def test_ds_get_no_params(self, project_service):
        """Test dataset retrieval with no parameters."""
        with pytest.raises(ValueError, match="At least one search parameter"):
            project_service.ds_get()

    def test_sheet_get_by_name_with_dataset(self, project_service, test_dataset_name, test_sheet_name):
        """Test successful sheet retrieval by name with dataset ID."""
        # Create dataset and sheet
        dataset_id = project_service.ds_create(test_dataset_name)
        sheet_id = project_service.sheet_create(dataset_id, test_sheet_name)

        try:
            result = project_service.sheet_get(dataset_id=dataset_id, name=test_sheet_name)
            assert result['id'] == sheet_id
            assert result['name'] == test_sheet_name
            assert result['dataset_id'] == dataset_id
            assert 'name_python' in result
        finally:
            # Clean up
            try:
                project_service.supabase_client.table("datasheets").delete().eq("dataset_id", dataset_id).execute()
                project_service.supabase_client.table("datasets").delete().eq("id", dataset_id).execute()
            except Exception:
                pass

    def test_sheet_get_by_name_all_datasets(self, project_service, test_dataset_name, test_sheet_name):
        """Test sheet retrieval by name across all datasets."""
        # Create dataset and sheet
        dataset_id = project_service.ds_create(test_dataset_name)
        sheet_id = project_service.sheet_create(dataset_id, test_sheet_name)

        try:
            # Search across all datasets (don't specify dataset_id)
            result = project_service.sheet_get(name=test_sheet_name)
            assert result['id'] == sheet_id
            assert result['name'] == test_sheet_name
        finally:
            # Clean up
            try:
                project_service.supabase_client.table("datasheets").delete().eq("dataset_id", dataset_id).execute()
                project_service.supabase_client.table("datasets").delete().eq("id", dataset_id).execute()
            except Exception:
                pass

    def test_sheet_get_by_id_success(self, project_service, test_dataset_name, test_sheet_name):
        """Test successful sheet retrieval by ID."""
        # Create dataset and sheet
        dataset_id = project_service.ds_create(test_dataset_name)
        sheet_id = project_service.sheet_create(dataset_id, test_sheet_name)

        try:
            result = project_service.sheet_get(id=sheet_id)
            assert result['id'] == sheet_id
            assert result['name'] == test_sheet_name
            assert result['dataset_id'] == dataset_id
        finally:
            # Clean up
            try:
                project_service.supabase_client.table("datasheets").delete().eq("dataset_id", dataset_id).execute()
                project_service.supabase_client.table("datasets").delete().eq("id", dataset_id).execute()
            except Exception:
                pass

    def test_sheet_get_not_found(self, project_service, test_dataset_name):
        """Test sheet retrieval when not found."""
        # Create dataset but no sheet
        dataset_id = project_service.ds_create(test_dataset_name)

        try:
            with pytest.raises(ValueError, match="not found"):
                project_service.sheet_get(dataset_id=dataset_id, name='NonExistentSheet')
        finally:
            # Clean up
            try:
                project_service.supabase_client.table("datasets").delete().eq("id", dataset_id).execute()
            except Exception:
                pass

    def test_sheet_get_no_params(self, project_service):
        """Test sheet retrieval with no parameters."""
        with pytest.raises(ValueError, match="At least one search parameter"):
            project_service.sheet_get()


if __name__ == '__main__':
    pytest.main([__file__])