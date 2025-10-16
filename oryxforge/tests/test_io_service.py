"""Tests for IOService."""

import pytest
import tempfile
import pandas as pd
from pathlib import Path

from ..services.io_service import IOService
from ..services.project_service import ProjectService
from ..services.iam import CredentialsManager
from ..services.utils import init_supabase_client
from .test_config import TEST_USER_ID, TEST_PROJECT_ID

try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


class TestIOService:
    """Test cases for IOService core functionality."""

    USER_ID = TEST_USER_ID
    PROJECT_ID = TEST_PROJECT_ID

    # Track created resources for cleanup
    created_datasets = []
    created_files = []  # Track combined name_python (e.g., "exploration.TestSheet")

    @pytest.fixture(scope="class", autouse=True)
    def cleanup_resources(self, supabase_client, test_project_id):
        """Cleanup all created resources after all tests complete."""
        yield

        # Clean up files using IOService (if we have a project and files to clean)
        if test_project_id and self.created_files:
            try:
                import tempfile
                from ..services.env_config import ProjectContext

                with tempfile.TemporaryDirectory() as temp_dir:
                    # Set context with explicit temp directory
                    ProjectContext.set(
                        user_id=self.USER_ID,
                        project_id=test_project_id,
                        working_dir=temp_dir
                    )

                    # Create IOService - reads from context
                    io_service = IOService()

                    # Delete tracked files
                    for name_python in self.created_files:
                        for delete_method in [io_service.delete_df, io_service.delete_chart,
                                             io_service.delete_markdown]:
                            try:
                                delete_method(name_python)
                                break  # Success - move to next file
                            except:
                                continue  # Try next delete method
            except Exception as e:
                print(f"Cleanup failed: {e}")
            finally:
                ProjectContext.clear()

        # Cleanup datasets (if any tracked - shouldn't be any since we use Exploration)
        for dataset_id in self.created_datasets:
            try:
                supabase_client.table("datasets").delete().eq("id", dataset_id).execute()
            except Exception:
                pass

        # Always clear tracking lists
        self.created_datasets.clear()
        self.created_files.clear()

    @pytest.fixture(scope="class")
    def supabase_client(self):
        """Get real Supabase client."""
        return init_supabase_client()

    @pytest.fixture(scope="class")
    def test_project_id(self):
        """Return the configured test project ID."""
        return self.PROJECT_ID

    @pytest.fixture
    def temp_working_dir(self):
        """Create temporary working directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def io_service(self, test_project_id, temp_working_dir):
        """Create IOService instance for testing."""
        # Set up project context with temp directory
        from ..services.env_config import ProjectContext
        ProjectContext.set(user_id=self.USER_ID, project_id=test_project_id, working_dir=temp_working_dir)

        # Create IOService - reads from context
        io_service = IOService()

        yield io_service

        # Clear context after test
        ProjectContext.clear()

    @pytest.fixture
    def sample_dataframe(self):
        """Create sample DataFrame for testing."""
        return pd.DataFrame({
            'name': ['Alice', 'Bob', 'Charlie'],
            'age': [25, 30, 35],
            'city': ['New York', 'London', 'Paris']
        })

    @pytest.fixture
    def sample_plotly_chart(self):
        """Create sample Plotly chart for testing."""
        if not PLOTLY_AVAILABLE:
            pytest.skip("Plotly not installed")

        fig = go.Figure(data=[go.Scatter(x=[1, 2, 3], y=[4, 5, 6], mode='lines+markers')])
        fig.update_layout(title='Test Chart', xaxis_title='X Axis', yaxis_title='Y Axis')
        return fig

    @pytest.fixture
    def sample_markdown(self):
        """Create sample markdown content for testing."""
        return """# Test Markdown

## Overview
This is a test markdown document.

### Features
- Feature 1
- Feature 2
- Feature 3

## Code Example
```python
def hello():
    print("Hello, World!")
```

## Conclusion
End of test document.
"""

    def track_dataset(self, dataset_id: str):
        """Track a dataset for cleanup."""
        if dataset_id not in self.created_datasets:
            self.created_datasets.append(dataset_id)

    def track_file(self, name_python: str):
        """Track a file for cleanup."""
        if name_python not in self.created_files:
            self.created_files.append(name_python)

    def test_save_and_load_roundtrip(self, io_service, sample_dataframe, temp_working_dir):
        """Test saving and loading a DataFrame roundtrip."""
        import time
        sheet_name = f"TestSheet{int(time.time())}"

        # Save DataFrame (using default 'Exploration' dataset)
        result = io_service.save_df_pd(sample_dataframe, sheet_name)

        # Track for cleanup (only track file, not exploration dataset)
        combined_name = f"{result['dataset_name_python']}.{result['sheet_name_python']}"
        self.track_file(combined_name)

        # Verify save result
        assert result['message'] == 'DataFrame saved successfully'
        assert 'dataset_id' in result
        assert 'sheet_id' in result
        assert result['shape'] == sample_dataframe.shape
        assert result['dataset_name_python'] == 'exploration'

        # Verify file exists
        path = Path(result['path'])
        assert path.exists()

        # Load DataFrame using dataset.sheet notation
        loaded_df = io_service.load_df_pd(combined_name)

        # Verify loaded DataFrame matches original
        pd.testing.assert_frame_equal(loaded_df, sample_dataframe)

    def test_save_empty_dataframe(self, io_service):
        """Test that saving empty DataFrame raises error."""
        empty_df = pd.DataFrame()

        with pytest.raises(ValueError, match="Cannot save empty DataFrame"):
            io_service.save_df_pd(empty_df, "TestSheet")

    def test_load_nonexistent_file(self, io_service):
        """Test loading from non-existent file raises error."""
        with pytest.raises(ValueError, match="not found"):
            io_service.load_df_pd("exploration.NonexistentSheet")

    def test_save_with_default_exploration_dataset(self, io_service, sample_dataframe):
        """Test saving with default 'Exploration' dataset."""
        import time
        sheet_name = f"test_exploration_sheet_{int(time.time())}"

        # Save without specifying dataset_name (should default to 'Exploration')
        result = io_service.save_df_pd(sample_dataframe, sheet_name)

        # Track for cleanup (only file, not dataset since we didn't create it)
        combined_name = f"{result['dataset_name_python']}.{result['sheet_name_python']}"
        self.track_file(combined_name)

        # Verify dataset name is 'exploration' (python name)
        assert 'exploration' in result['dataset_name_python'].lower()

        # Verify file exists
        path = Path(result['path'])
        assert path.exists()

    def test_delete_df(self, io_service, sample_dataframe):
        """Test deleting a DataFrame and its metadata."""
        import time
        sheet_name = f"TestDeleteSheet{int(time.time())}"

        # Save DataFrame (using default 'Exploration' dataset)
        result = io_service.save_df_pd(sample_dataframe, sheet_name)

        # Don't track - test will delete it

        # Verify file exists
        path = Path(result['path'])
        assert path.exists()

        # Delete DataFrame
        combined_name = f"{result['dataset_name_python']}.{result['sheet_name_python']}"
        delete_result = io_service.delete_df(combined_name)

        # Verify deletion result
        assert delete_result['message'] == 'DataFrame deleted successfully'
        assert delete_result['file_deleted'] is True
        assert delete_result['sheet_deleted'] is True

        # Verify file no longer exists
        assert not path.exists()

        # Verify can't load anymore
        with pytest.raises(ValueError, match="not found"):
            io_service.load_df_pd(combined_name)

    @pytest.mark.skipif(not PLOTLY_AVAILABLE, reason="Plotly not installed")
    def test_save_and_load_chart(self, io_service, sample_plotly_chart):
        """Test saving and loading a Plotly chart."""
        import time
        sheet_name = f"TestChart{int(time.time())}"

        # Save chart (using default 'Exploration' dataset)
        result = io_service.save_chart_plotly(sample_plotly_chart, sheet_name)

        # Track for cleanup
        combined_name = f"{result['dataset_name_python']}.{result['sheet_name_python']}"
        self.track_file(combined_name)

        # Verify save result
        assert result['message'] == 'Chart saved successfully'
        assert 'dataset_id' in result
        assert 'sheet_id' in result

        # Verify file exists
        path = Path(result['path'])
        assert path.exists()
        assert path.suffix == '.html'

        # Verify HTML contains CDN reference
        with open(path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        assert 'cdn.plot.ly' in html_content or 'plotly' in html_content.lower()

        # Load chart path only
        loaded_path = io_service.load_chart_plotly(combined_name, return_html=False)
        assert loaded_path == str(path)

        # Load chart with HTML content
        loaded_data = io_service.load_chart_plotly(combined_name, return_html=True)
        assert 'path' in loaded_data
        assert 'html_content' in loaded_data
        assert loaded_data['path'] == str(path)
        assert 'plotly' in loaded_data['html_content'].lower()

    @pytest.mark.skipif(not PLOTLY_AVAILABLE, reason="Plotly not installed")
    def test_delete_chart(self, io_service, sample_plotly_chart):
        """Test deleting a Plotly chart."""
        import time
        sheet_name = f"TestDeleteChart{int(time.time())}"

        # Save chart (using default 'Exploration' dataset)
        result = io_service.save_chart_plotly(sample_plotly_chart, sheet_name)

        # Don't track - test will delete it

        # Verify file exists
        path = Path(result['path'])
        assert path.exists()

        # Delete chart
        combined_name = f"{result['dataset_name_python']}.{result['sheet_name_python']}"
        delete_result = io_service.delete_chart(combined_name)

        # Verify deletion result
        assert delete_result['message'] == 'Chart deleted successfully'
        assert delete_result['file_deleted'] is True
        assert delete_result['sheet_deleted'] is True

        # Verify file no longer exists
        assert not path.exists()

        # Verify can't load anymore
        with pytest.raises(ValueError, match="not found"):
            io_service.load_chart_plotly(combined_name)

    def test_save_and_load_markdown(self, io_service, sample_markdown):
        """Test saving and loading markdown content."""
        import time
        sheet_name = f"TestMarkdown{int(time.time())}"

        # Save markdown (using default 'Exploration' dataset)
        result = io_service.save_markdown(sample_markdown, sheet_name)

        # Track for cleanup
        combined_name = f"{result['dataset_name_python']}.{result['sheet_name_python']}"
        self.track_file(combined_name)

        # Verify save result
        assert result['message'] == 'Markdown saved successfully'
        assert 'dataset_id' in result
        assert 'sheet_id' in result
        assert result['length'] == len(sample_markdown)

        # Verify file exists
        path = Path(result['path'])
        assert path.exists()
        assert path.suffix == '.md'

        # Load markdown
        loaded_content = io_service.load_markdown(combined_name)
        assert loaded_content == sample_markdown

    def test_save_empty_markdown(self, io_service):
        """Test that saving empty markdown raises error."""
        with pytest.raises(ValueError, match="Cannot save empty markdown content"):
            io_service.save_markdown("", "TestSheet")

        with pytest.raises(ValueError, match="Cannot save empty markdown content"):
            io_service.save_markdown("   ", "TestSheet")

    def test_delete_markdown(self, io_service, sample_markdown):
        """Test deleting markdown content."""
        import time
        sheet_name = f"TestDeleteMarkdown{int(time.time())}"

        # Save markdown (using default 'Exploration' dataset)
        result = io_service.save_markdown(sample_markdown, sheet_name)

        # Don't track - test will delete it

        # Verify file exists
        path = Path(result['path'])
        assert path.exists()

        # Delete markdown
        combined_name = f"{result['dataset_name_python']}.{result['sheet_name_python']}"
        delete_result = io_service.delete_markdown(combined_name)

        # Verify deletion result
        assert delete_result['message'] == 'Markdown deleted successfully'
        assert delete_result['file_deleted'] is True
        assert delete_result['sheet_deleted'] is True

        # Verify file no longer exists
        assert not path.exists()

        # Verify can't load anymore
        with pytest.raises(ValueError, match="not found"):
            io_service.load_markdown(combined_name)


if __name__ == '__main__':
    pytest.main([__file__])
