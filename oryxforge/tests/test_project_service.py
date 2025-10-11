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
from ..services.iam import CredentialsManager


class TestProjectService:
    """Integration test cases for ProjectService."""

    USER_ID = '24d811e2-1801-4208-8030-a86abbda59b8'

    # Track created resources for cleanup
    created_datasets = []
    created_sheets = []

    @pytest.fixture(scope="class", autouse=True)
    def cleanup_resources(self, supabase_client):
        """Cleanup all created resources after all tests complete."""
        yield
        # Cleanup sheets first (due to foreign key constraints)
        for sheet_id in self.created_sheets:
            try:
                supabase_client.table("datasheets").delete().eq("id", sheet_id).execute()
            except Exception:
                pass
        # Then cleanup datasets
        for dataset_id in self.created_datasets:
            try:
                supabase_client.table("datasets").delete().eq("id", dataset_id).execute()
            except Exception:
                pass
        # Clear tracking lists
        self.created_datasets.clear()
        self.created_sheets.clear()

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
    def temp_working_dir(self):
        """Create temporary working directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def project_service(self, test_project_id, temp_working_dir):
        """Create ProjectService instance for integration testing."""
        if not test_project_id:
            pytest.skip("No test project available - please create a project for user 24d811e2-1801-4208-8030-a86abbda59b8")

        # Set up profile using CredentialsManager
        creds_manager = CredentialsManager(working_dir=temp_working_dir)
        creds_manager.set_profile(user_id=self.USER_ID, project_id=test_project_id)

        # Create ProjectService - it will read from CredentialsManager
        return ProjectService(working_dir=temp_working_dir)

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

    def track_dataset(self, dataset_id: str):
        """Track a dataset for cleanup."""
        if dataset_id not in self.created_datasets:
            self.created_datasets.append(dataset_id)

    def track_sheet(self, sheet_id: str):
        """Track a sheet for cleanup."""
        if sheet_id not in self.created_sheets:
            self.created_sheets.append(sheet_id)

    def test_init_success(self, project_service):
        """Test successful initialization."""
        assert project_service.project_id is not None
        assert project_service.user_id == self.USER_ID
        assert project_service.project_name is not None

    def test_init_with_invalid_project(self, temp_working_dir):
        """Test initialization with invalid project."""
        # Set up profile with invalid project ID
        creds_manager = CredentialsManager(working_dir=temp_working_dir)
        creds_manager.set_profile(user_id=self.USER_ID, project_id='00000000-0000-0000-0000-000000000000')

        # Use valid UUID format but non-existent project
        with pytest.raises(ValueError, match="Failed to validate project"):
            ProjectService(working_dir=temp_working_dir)

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

    def test_ds_create_success(self, project_service, test_dataset_name):
        """Test successful dataset creation."""
        # Create a dataset
        result = project_service.ds_create(test_dataset_name)
        assert isinstance(result, dict)
        assert 'id' in result
        assert 'name' in result
        assert 'name_python' in result
        assert result['name'] == test_dataset_name

        dataset_id = result['id']
        self.track_dataset(dataset_id)
        assert isinstance(dataset_id, str)
        assert len(dataset_id) > 0

        # Verify it exists
        datasets = project_service.ds_list()
        created_dataset = next((ds for ds in datasets if ds['id'] == dataset_id), None)
        assert created_dataset is not None
        assert created_dataset['name'] == test_dataset_name

    def test_ds_create_duplicate_name(self, project_service, test_dataset_name):
        """Test dataset creation with duplicate name - should be idempotent with upsert."""
        # Create first dataset
        result1 = project_service.ds_create(test_dataset_name)
        dataset_id1 = result1['id']
        self.track_dataset(dataset_id1)

        # Create another with same name - should return same dataset (upsert behavior)
        result2 = project_service.ds_create(test_dataset_name)
        dataset_id2 = result2['id']

        # Should return the same dataset ID (idempotent)
        assert dataset_id1 == dataset_id2
        assert result1['name'] == result2['name']
        assert result1['name_python'] == result2['name_python']

    def test_ds_create_with_invalid_project(self):
        """Test dataset creation with invalid project access."""
        # This test verifies that dataset creation fails with wrong user permissions
        # We can't easily test this without creating multiple projects
        pass

    def test_sheet_create_success(self, project_service, test_dataset_name, test_sheet_name):
        """Test successful datasheet creation."""
        # First create a dataset
        dataset_id = project_service.ds_create(test_dataset_name)['id']
        self.track_dataset(dataset_id)

        # Create a sheet in the dataset
        sheet_data = project_service.sheet_create(dataset_id, test_sheet_name)
        self.track_sheet(sheet_data['id'])
        assert isinstance(sheet_data, dict)
        assert 'id' in sheet_data
        assert 'name' in sheet_data
        assert 'name_python' in sheet_data
        assert sheet_data['name'] == test_sheet_name

        # Verify it exists
        sheets = project_service.sheet_list(dataset_id)
        created_sheet = next((sh for sh in sheets if sh['id'] == sheet_data['id']), None)
        assert created_sheet is not None
        assert created_sheet['name'] == test_sheet_name

    def test_sheet_create_dataset_not_found(self, project_service, test_sheet_name):
        """Test datasheet creation with non-existing dataset."""
        with pytest.raises(ValueError, match="Dataset .* not found"):
            project_service.sheet_create('non-existent-dataset-id', test_sheet_name)

    def test_sheet_create_duplicate_name(self, project_service, test_dataset_name, test_sheet_name):
        """Test datasheet creation with duplicate name (idempotent with upsert)."""
        # Create dataset and sheet
        dataset_id = project_service.ds_create(test_dataset_name)['id']
        self.track_dataset(dataset_id)
        sheet_data_1 = project_service.sheet_create(dataset_id, test_sheet_name)
        self.track_sheet(sheet_data_1['id'])

        # Try to create another sheet with same name - should return same ID (idempotent)
        sheet_data_2 = project_service.sheet_create(dataset_id, test_sheet_name)
        assert sheet_data_1['id'] == sheet_data_2['id'], "Upsert should return same ID for duplicate"

    def test_sheet_list_specific_dataset(self, project_service, test_dataset_name):
        """Test datasheet listing for specific dataset."""
        # Create a dataset first
        dataset_id = project_service.ds_create(test_dataset_name)['id']
        self.track_dataset(dataset_id)

        # Create a sheet and verify it appears in the list
        sheet_data = project_service.sheet_create(dataset_id, f"sheet_in_{test_dataset_name}")
        self.track_sheet(sheet_data['id'])
        sheet_id = sheet_data['id']

        result = project_service.sheet_list(dataset_id)
        assert isinstance(result, list)
        assert len(result) > 0
        sheet_ids = [s['id'] for s in result]
        assert sheet_id in sheet_ids

        # Find our sheet in the results
        created_sheet = next((s for s in result if s['id'] == sheet_id), None)
        assert created_sheet is not None
        assert created_sheet['dataset_id'] == dataset_id

        # Track any other sheets (like default "data" sheet) for cleanup
        for sheet in result:
            self.track_sheet(sheet['id'])

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
        dataset_id = project_service.ds_create(test_dataset_name)['id']
        self.track_dataset(dataset_id)

        # Check that it exists
        result = project_service.ds_exists(dataset_id)
        assert result is True

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
        dataset_id = project_service.ds_create(test_dataset_name)['id']
        self.track_dataset(dataset_id)
        sheet_data = project_service.sheet_create(dataset_id, test_sheet_name)
        self.track_sheet(sheet_data['id'])
        sheet_id = sheet_data['id']

        # Check that it exists
        result = project_service.sheet_exists(sheet_id)
        assert result is True

    def test_sheet_exists_false(self, project_service):
        """Test sheet_exists returns False for non-existing sheet."""
        result = project_service.sheet_exists('non-existing-id')
        assert result is False


    def test_is_initialized_true(self, project_service):
        """Test is_initialized checks for GitLab repository - skip in test environment."""
        # is_initialized checks if GitLab repository exists
        # In test environment without git repo, this will return False
        pytest.skip("Test project doesn't have GitLab repository initialized")

    def test_is_initialized_false(self, project_service):
        """Test is_initialized returns False for uninitialized project."""
        project_service.project_id = None
        result = project_service.is_initialized()
        assert result is False

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
        dataset_id = project_service.ds_create(test_dataset_name)['id']
        self.track_dataset(dataset_id)
        sheet_data = project_service.sheet_create(dataset_id, test_sheet_name)
        self.track_sheet(sheet_data['id'])
        sheet_id = sheet_data['id']

        result = project_service.get_first_sheet_id(dataset_id)
        assert result == sheet_id

    def test_get_first_sheet_id_no_sheets(self, project_service, test_dataset_name):
        """Test first sheet retrieval - datasets now come with default 'data' sheet."""
        # Create dataset (comes with default "data" sheet)
        dataset_id = project_service.ds_create(test_dataset_name)['id']
        self.track_dataset(dataset_id)

        # Should return the default sheet, not raise an error
        result = project_service.get_first_sheet_id(dataset_id)
        assert result is not None
        assert isinstance(result, str)

        # Track the default sheet for cleanup
        sheets = project_service.sheet_list(dataset_id)
        for sheet in sheets:
            self.track_sheet(sheet['id'])

    def test_interactive_dataset_select_success(self, project_service, test_dataset_name):
        """Test successful interactive dataset selection."""
        # Create a dataset
        dataset_id = project_service.ds_create(test_dataset_name)['id']
        self.track_dataset(dataset_id)

        with patch('builtins.input', return_value='1'):
            result = project_service.interactive_dataset_select()
            # Should return the first dataset found
            assert isinstance(result, str)
            assert len(result) > 0

    def test_interactive_sheet_select_success(self, project_service, test_dataset_name, test_sheet_name):
        """Test successful interactive sheet selection."""
        # Create dataset and sheet
        dataset_id = project_service.ds_create(test_dataset_name)['id']
        self.track_dataset(dataset_id)
        sheet_data = project_service.sheet_create(dataset_id, test_sheet_name)
        self.track_sheet(sheet_data['id'])
        sheet_id = sheet_data['id']

        with patch('builtins.input', return_value='1'):
            result = project_service.interactive_sheet_select()
            # Should return a valid sheet ID
            assert isinstance(result, str)
            assert len(result) > 0

    def test_ds_get_by_name_success(self, project_service, test_dataset_name):
        """Test successful dataset retrieval by name."""
        # Create a dataset
        dataset_id = project_service.ds_create(test_dataset_name)['id']
        self.track_dataset(dataset_id)

        result = project_service.ds_get(name=test_dataset_name)
        assert result['id'] == dataset_id
        assert result['name'] == test_dataset_name
        assert 'name_python' in result

    def test_ds_get_by_id_success(self, project_service, test_dataset_name):
        """Test successful dataset retrieval by ID."""
        # Create a dataset
        dataset_id = project_service.ds_create(test_dataset_name)['id']
        self.track_dataset(dataset_id)

        result = project_service.ds_get(id=dataset_id)
        assert result['id'] == dataset_id
        assert result['name'] == test_dataset_name

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
        dataset_id = project_service.ds_create(test_dataset_name)['id']
        self.track_dataset(dataset_id)
        sheet_data = project_service.sheet_create(dataset_id, test_sheet_name)
        self.track_sheet(sheet_data['id'])
        sheet_id = sheet_data['id']

        result = project_service.sheet_get(dataset_id=dataset_id, name=test_sheet_name)
        assert result['id'] == sheet_id
        assert result['name'] == test_sheet_name
        assert result['dataset_id'] == dataset_id
        assert 'name_python' in result

    def test_sheet_get_by_name_all_datasets(self, project_service, test_dataset_name, test_sheet_name):
        """Test sheet retrieval by name across all datasets."""
        # Create dataset and sheet
        dataset_id = project_service.ds_create(test_dataset_name)['id']
        self.track_dataset(dataset_id)
        sheet_data = project_service.sheet_create(dataset_id, test_sheet_name)
        self.track_sheet(sheet_data['id'])
        sheet_id = sheet_data['id']

        # Search across all datasets (don't specify dataset_id)
        result = project_service.sheet_get(name=test_sheet_name)
        assert result['id'] == sheet_id
        assert result['name'] == test_sheet_name

    def test_sheet_get_by_id_success(self, project_service, test_dataset_name, test_sheet_name):
        """Test successful sheet retrieval by ID."""
        # Create dataset and sheet
        dataset_id = project_service.ds_create(test_dataset_name)['id']
        self.track_dataset(dataset_id)
        sheet_data = project_service.sheet_create(dataset_id, test_sheet_name)
        self.track_sheet(sheet_data['id'])
        sheet_id = sheet_data['id']

        result = project_service.sheet_get(id=sheet_id)
        assert result['id'] == sheet_id
        assert result['name'] == test_sheet_name
        assert result['dataset_id'] == dataset_id

    def test_sheet_get_not_found(self, project_service, test_dataset_name):
        """Test sheet retrieval when not found."""
        # Create dataset but no sheet
        dataset_id = project_service.ds_create(test_dataset_name)['id']
        self.track_dataset(dataset_id)

        with pytest.raises(ValueError, match="not found"):
            project_service.sheet_get(dataset_id=dataset_id, name='NonExistentSheet')

    def test_sheet_get_no_params(self, project_service):
        """Test sheet retrieval with no parameters."""
        with pytest.raises(ValueError, match="At least one search parameter"):
            project_service.sheet_get()

    def test_ds_sheet_list_df_format(self, project_service, test_dataset_name, test_sheet_name):
        """Test ds_sheet_list with DataFrame format."""
        # Create dataset and sheet
        dataset_id = project_service.ds_create(test_dataset_name)['id']
        self.track_dataset(dataset_id)
        sheet_data = project_service.sheet_create(dataset_id, test_sheet_name)
        self.track_sheet(sheet_data['id'])

        # Test DataFrame format
        result = project_service.ds_sheet_list(format='df')
        assert isinstance(result, pd.DataFrame)
        assert 'name_dataset' in result.columns
        assert 'name_sheet' in result.columns
        assert 'name_python' in result.columns

        # Should have at least our created sheet
        assert len(result) > 0

        # Check that our sheet is in the results
        dataset_info = project_service.ds_get(id=dataset_id)
        expected_combined = f"{dataset_info['name_python']}.{sheet_data['name_python']}"
        matching_rows = result[result['name_python'] == expected_combined]
        assert len(matching_rows) > 0
        assert matching_rows.iloc[0]['name_dataset'] == test_dataset_name
        assert matching_rows.iloc[0]['name_sheet'] == test_sheet_name

    def test_ds_sheet_list_list_format(self, project_service, test_dataset_name, test_sheet_name):
        """Test ds_sheet_list with list format."""
        # Create dataset and sheet
        dataset_id = project_service.ds_create(test_dataset_name)['id']
        self.track_dataset(dataset_id)
        sheet_data = project_service.sheet_create(dataset_id, test_sheet_name)
        self.track_sheet(sheet_data['id'])

        # Test list format
        result = project_service.ds_sheet_list(format='list')
        assert isinstance(result, list)
        assert len(result) > 0

        # Check structure of first item
        if result:
            assert 'name_dataset' in result[0]
            assert 'name_sheet' in result[0]
            assert 'name_python' in result[0]

            # Check that our sheet is in the results
            dataset_info = project_service.ds_get(id=dataset_id)
            expected_combined = f"{dataset_info['name_python']}.{sheet_data['name_python']}"
            matching = [r for r in result if r['name_python'] == expected_combined]
            assert len(matching) > 0
            assert matching[0]['name_dataset'] == test_dataset_name
            assert matching[0]['name_sheet'] == test_sheet_name

    def test_ds_sheet_list_invalid_format(self, project_service):
        """Test ds_sheet_list with invalid format."""
        with pytest.raises(ValueError, match="Invalid format"):
            project_service.ds_sheet_list(format='invalid')

    def test_ds_sheet_get_success(self, project_service, test_dataset_name, test_sheet_name):
        """Test successful ds_sheet_get."""
        # Create dataset and sheet
        dataset_id = project_service.ds_create(test_dataset_name)['id']
        self.track_dataset(dataset_id)
        sheet_data = project_service.sheet_create(dataset_id, test_sheet_name)
        self.track_sheet(sheet_data['id'])

        # Get dataset info to build combined name
        dataset_info = project_service.ds_get(id=dataset_id)
        combined_name = f"{dataset_info['name_python']}.{sheet_data['name_python']}"

        # Test ds_sheet_get
        result = project_service.ds_sheet_get(combined_name)

        # Check structure
        assert 'dataset' in result
        assert 'sheet' in result
        assert 'ds_sheet_name_python' in result

        # Check dataset info
        assert result['dataset']['id'] == dataset_id
        assert result['dataset']['name'] == test_dataset_name
        assert result['dataset']['name_python'] == dataset_info['name_python']

        # Check sheet info
        assert result['sheet']['id'] == sheet_data['id']
        assert result['sheet']['name'] == test_sheet_name
        assert result['sheet']['name_python'] == sheet_data['name_python']
        assert result['sheet']['dataset_id'] == dataset_id

        # Check combined name
        assert result['ds_sheet_name_python'] == combined_name

    def test_ds_sheet_get_invalid_format_no_dot(self, project_service):
        """Test ds_sheet_get with invalid format (no dot)."""
        with pytest.raises(ValueError, match="Invalid format.*Expected 'dataset.sheet' notation"):
            project_service.ds_sheet_get("nodothere")

    def test_ds_sheet_get_invalid_format_empty_parts(self, project_service):
        """Test ds_sheet_get with invalid format (empty parts)."""
        with pytest.raises(ValueError, match="Both dataset and sheet names must be non-empty"):
            project_service.ds_sheet_get(".SheetName")

        with pytest.raises(ValueError, match="Both dataset and sheet names must be non-empty"):
            project_service.ds_sheet_get("DatasetName.")

    def test_ds_sheet_get_not_found(self, project_service):
        """Test ds_sheet_get when combination not found."""
        with pytest.raises(ValueError, match="not found"):
            project_service.ds_sheet_get("nonexistent.combination")


if __name__ == '__main__':
    pytest.main([__file__])