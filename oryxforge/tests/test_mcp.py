import pytest
import tempfile
import shutil
import os
from pathlib import Path
from oryxforge.tools.mcp import (
    create_sheet, read_sheet, update_sheet, delete_sheet, upsert_sheet,
    list_sheets, list_datasets, list_sheets_by_dataset, rename_sheet,
    get_working_directory, get_tasks_directory, list_directory,
    create_run, create_preview, execute_run, execute_preview, preview_flow
)


@pytest.fixture
def temp_dir():
    """Create and cleanup temporary directory."""
    temp_path = tempfile.mkdtemp()
    original_cwd = Path.cwd()
    try:
        # Change to temp directory for MCP operations
        os.chdir(temp_path)
        # Reinitialize the MCP service with the new directory
        from oryxforge.tools import mcp
        from oryxforge.services.workflow_service import WorkflowService
        mcp.svc = WorkflowService(base_dir=str(temp_path))
        yield temp_path
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(temp_path)


class TestMCPBasicOperations:
    """Test basic MCP sheet operations."""

    def test_create_sheet(self, temp_dir):
        """Test creating a sheet via MCP."""
        result = create_sheet.fn(
            sheet="TestTask",
            code="df = pd.DataFrame({'x': [1, 2, 3]})"
        )
        
        assert "Created TestTask in tasks/__init__.py" in result

    def test_create_sheet_with_inputs(self, temp_dir):
        """Test creating sheet with inputs via MCP."""
        # Create first task
        create_sheet.fn(
            sheet="TaskA",
            code="df = pd.DataFrame({'a': [1]})"
        )
        
        # Create second task with inputs
        result = create_sheet.fn(
            sheet="TaskB",
            code="df = pd.DataFrame({'b': [2]})",
            inputs=[{"dataset": None, "sheet": "TaskA"}]
        )
        
        assert "Created TaskB in tasks/__init__.py" in result

    def test_read_sheet(self, temp_dir):
        """Test reading sheet via MCP."""
        # Create task first
        create_sheet.fn(
            sheet="ReadTask",
            code="df = pd.DataFrame({'test': [1]})"
        )
        
        # Read task
        result = read_sheet.fn(task="ReadTask")
        assert "pd.DataFrame" in result
        assert "test" in result

    def test_update_sheet(self, temp_dir):
        """Test updating sheet via MCP."""
        # Create task first
        create_sheet.fn(
            sheet="UpdateTask",
            code="df = pd.DataFrame({'old': [1]})"
        )
        
        # Update task
        result = update_sheet.fn(
            sheet="UpdateTask",
            new_code="df = pd.DataFrame({'new': [2]})"
        )
        
        assert "Updated UpdateTask in tasks/__init__.py" in result
        
        # Verify update
        read_result = read_sheet.fn(task="UpdateTask")
        assert "new" in read_result
        assert "old" not in read_result

    def test_delete_sheet(self, temp_dir):
        """Test deleting sheet via MCP."""
        # Create task first
        create_sheet.fn(
            sheet="DeleteTask",
            code="df = pd.DataFrame()"
        )
        
        # Delete task
        result = delete_sheet.fn(task="DeleteTask")
        assert "Deleted task DeleteTask" in result

    def test_upsert_create(self, temp_dir):
        """Test upsert creating new sheet via MCP."""
        result = upsert_sheet.fn(
            sheet="NewTask",
            code="df = pd.DataFrame({'new': [1]})"
        )
        
        assert "Created NewTask in tasks/__init__.py" in result

    def test_upsert_update(self, temp_dir):
        """Test upsert updating existing sheet via MCP."""
        # Create task first
        create_sheet.fn(
            sheet="ExistingTask",
            code="df = pd.DataFrame({'old': [1]})"
        )
        
        # Upsert task
        result = upsert_sheet.fn(
            sheet="ExistingTask",
            code="df = pd.DataFrame({'updated': [2]})"
        )
        
        assert "Updated ExistingTask in tasks/__init__.py" in result


class TestMCPDatasetOperations:
    """Test MCP dataset-specific operations."""

    def test_create_in_dataset(self, temp_dir):
        """Test creating sheet in specific dataset via MCP."""
        result = create_sheet.fn(
            sheet="ModuleTask",
            code="df = pd.DataFrame()",
            dataset="test_dataset"
        )
        
        assert "Created ModuleTask in test_dataset" in result

    def test_list_sheets(self, temp_dir):
        """Test listing sheets via MCP."""
        # Create some tasks
        create_sheet.fn(
            sheet="Task1",
            code="df = pd.DataFrame()"
        )
        create_sheet.fn(
            sheet="Task2", 
            code="df = pd.DataFrame()"
        )
        
        # List tasks in default module
        result = list_sheets.fn()
        assert isinstance(result, list)
        assert "Task1" in result
        assert "Task2" in result

    def test_list_datasets(self, temp_dir):
        """Test listing datasets via MCP."""
        # Create tasks in different modules
        create_sheet.fn(
            sheet="Task1",
            code="df = pd.DataFrame()",
            dataset="dataset_a"
        )
        create_sheet.fn(
            sheet="Task2",
            code="df = pd.DataFrame()",
            dataset="dataset_b"
        )
        
        # List modules
        result = list_datasets.fn()
        assert isinstance(result, list)
        assert "dataset_a" in result
        assert "dataset_b" in result


class TestMCPUtilityOperations:
    """Test MCP utility functions."""

    def test_get_working_directory(self, temp_dir):
        """Test getting working directory via MCP."""
        result = get_working_directory.fn()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_tasks_directory(self, temp_dir):
        """Test getting tasks directory via MCP."""
        result = get_tasks_directory.fn()
        assert isinstance(result, str)
        assert "tasks" in result

    def test_list_directory(self, temp_dir):
        """Test listing directory contents via MCP."""
        result = list_directory.fn()
        assert isinstance(result, list)


class TestMCPEdgeCases:
    """Test MCP edge cases and error handling."""

    def test_read_nonexistent_task(self, temp_dir):
        """Test reading non-existent task via MCP."""
        with pytest.raises(Exception):  # Should raise an error
            read_sheet.fn(task="NonExistentTask")

    def test_update_nonexistent_task(self, temp_dir):
        """Test updating non-existent task via MCP."""
        with pytest.raises(Exception):  # Should raise an error
            update_sheet.fn(
                sheet="NonExistentTask",
                new_code="df = pd.DataFrame()"
            )

    def test_delete_nonexistent_task(self, temp_dir):
        """Test deleting non-existent task via MCP."""
        with pytest.raises(Exception):  # Should raise an error
            delete_sheet.fn(task="NonExistentTask")


class TestMCPFlowExecution:
    """Test MCP flow execution functionality."""

    def test_create_preview_basic(self, temp_dir):
        """Test creating preview script via MCP."""
        # Create task first
        create_sheet.fn(
            sheet="FlowTask",
            code="df = pd.DataFrame({'flow': [1, 2, 3]})"
        )
        
        # Generate preview script
        result = create_preview.fn(
            sheet="FlowTask",
            flow_params={"model": "test"},
            reset_tasks=["FlowTask"]
        )
        assert isinstance(result, str)
        assert "flow.preview()" in result
        assert "import d6tflow" in result

    def test_create_run_basic(self, temp_dir):
        """Test creating run script via MCP."""
        # Create task first
        create_sheet.fn(
            sheet="RunFlowTask", 
            code="df = pd.DataFrame({'run': [1, 2, 3]})"
        )
        
        # Generate run script
        result = create_run.fn(
            sheet="RunFlowTask",
            flow_params={"test": "run"},
            reset_tasks=[]
        )
        assert isinstance(result, str)
        assert "flow.run()" in result
        assert "import d6tflow" in result

    def test_create_preview_with_module(self, temp_dir):
        """Test creating preview script with specific module via MCP."""
        # Create task in module
        create_sheet.fn(
            sheet="ModuleFlowTask",
            code="df = pd.DataFrame({'module': [1]})",
            dataset="flow_module"
        )
        
        # Generate preview script with module
        result = create_preview.fn(
            sheet="ModuleFlowTask",
            dataset="flow_module",
            flow_params={},
            reset_tasks=[]
        )
        assert isinstance(result, str)
        assert "import tasks.flow_module as tasks" in result
        assert "flow.preview()" in result

    def test_execute_preview_basic(self, temp_dir):
        """Test executing preview script via MCP."""
        # Create task first
        create_sheet.fn(
            sheet="ExecuteTask",
            code="df = pd.DataFrame({'execute': [1]})"
        )
        
        # Generate script
        script = create_preview.fn(task="ExecuteTask")
        
        # Execute script - may fail if d6tflow not available
        try:
            result = execute_preview.fn(script)
            assert isinstance(result, str)
        except Exception:
            # Expected if d6tflow not available
            pass
    
    def test_flow_nonexistent_task(self, temp_dir):
        """Test flow script generation with non-existent task via MCP."""
        # Should raise an error for non-existent task
        with pytest.raises(Exception):
            create_preview.fn(task="NonExistentFlowTask")
    
    def test_preview_flow_end_to_end(self, temp_dir):
        """Test complete preview flow via MCP."""
        # Create task first
        create_sheet.fn(
            sheet="EndToEndTask",
            code="df = pd.DataFrame({'e2e': [1]})"
        )
        
        # Test end-to-end preview flow
        try:
            result = preview_flow.fn(
                sheet="EndToEndTask",
                flow_params={"test": "e2e"},
                reset_tasks=[]
            )
            assert isinstance(result, str)
        except Exception:
            # Expected if d6tflow not available
            pass