import pytest
import tempfile
import shutil
import os
from pathlib import Path
from oryxforge.tools.mcp import (
    create_task, read_task, update_task, delete_task, upsert_task,
    list_tasks, list_modules, list_tasks_by_module, rename_task,
    get_working_directory, get_tasks_directory, list_directory
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
        from oryxforge.services.task_service import TaskService
        mcp.svc = TaskService(base_dir=str(temp_path))
        yield temp_path
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(temp_path)


class TestMCPBasicOperations:
    """Test basic MCP task operations."""

    def test_create_task(self, temp_dir):
        """Test creating a task via MCP."""
        result = create_task.fn(
            task="TestTask",
            code="df = pd.DataFrame({'x': [1, 2, 3]})"
        )
        
        assert "Created task TestTask" in result
        assert "tasks/__init__.py" in result

    def test_create_task_with_inputs(self, temp_dir):
        """Test creating task with inputs via MCP."""
        # Create first task
        create_task.fn(
            task="TaskA",
            code="df = pd.DataFrame({'a': [1]})"
        )
        
        # Create second task with inputs
        result = create_task.fn(
            task="TaskB", 
            code="df = pd.DataFrame({'b': [2]})",
            inputs=["TaskA"]
        )
        
        assert "Created task TaskB" in result

    def test_read_task(self, temp_dir):
        """Test reading task via MCP."""
        # Create task first
        create_task.fn(
            task="ReadTask",
            code="df = pd.DataFrame({'test': [1]})"
        )
        
        # Read task
        result = read_task.fn(task="ReadTask")
        assert "pd.DataFrame" in result
        assert "test" in result

    def test_update_task(self, temp_dir):
        """Test updating task via MCP."""
        # Create task first
        create_task.fn(
            task="UpdateTask",
            code="df = pd.DataFrame({'old': [1]})"
        )
        
        # Update task
        result = update_task.fn(
            task="UpdateTask",
            new_code="df = pd.DataFrame({'new': [2]})"
        )
        
        assert "Updated task UpdateTask" in result
        
        # Verify update
        read_result = read_task.fn(task="UpdateTask")
        assert "new" in read_result
        assert "old" not in read_result

    def test_delete_task(self, temp_dir):
        """Test deleting task via MCP."""
        # Create task first
        create_task.fn(
            task="DeleteTask",
            code="df = pd.DataFrame()"
        )
        
        # Delete task
        result = delete_task.fn(task="DeleteTask")
        assert "Deleted task DeleteTask" in result

    def test_upsert_create(self, temp_dir):
        """Test upsert creating new task via MCP."""
        result = upsert_task.fn(
            task="NewTask",
            code="df = pd.DataFrame({'new': [1]})"
        )
        
        assert "Upserted task NewTask" in result

    def test_upsert_update(self, temp_dir):
        """Test upsert updating existing task via MCP."""
        # Create task first
        create_task.fn(
            task="ExistingTask",
            code="df = pd.DataFrame({'old': [1]})"
        )
        
        # Upsert task
        result = upsert_task.fn(
            task="ExistingTask",
            code="df = pd.DataFrame({'updated': [2]})"
        )
        
        assert "Upserted task ExistingTask" in result


class TestMCPModuleOperations:
    """Test MCP module-specific operations."""

    def test_create_in_module(self, temp_dir):
        """Test creating task in specific module via MCP."""
        result = create_task.fn(
            task="ModuleTask",
            code="df = pd.DataFrame()",
            module="test_module"
        )
        
        assert "Created task ModuleTask" in result
        assert "test_module" in result

    def test_list_tasks(self, temp_dir):
        """Test listing tasks via MCP."""
        # Create some tasks
        create_task.fn(
            task="Task1",
            code="df = pd.DataFrame()"
        )
        create_task.fn(
            task="Task2", 
            code="df = pd.DataFrame()"
        )
        
        # List tasks in default module
        result = list_tasks.fn()
        assert isinstance(result, list)
        assert "Task1" in result
        assert "Task2" in result

    def test_list_modules(self, temp_dir):
        """Test listing modules via MCP."""
        # Create tasks in different modules
        create_task.fn(
            task="Task1",
            code="df = pd.DataFrame()",
            module="module_a"
        )
        create_task.fn(
            task="Task2",
            code="df = pd.DataFrame()",
            module="module_b"
        )
        
        # List modules
        result = list_modules.fn()
        assert isinstance(result, list)
        assert "module_a" in result
        assert "module_b" in result


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
            read_task.fn(task="NonExistentTask")

    def test_update_nonexistent_task(self, temp_dir):
        """Test updating non-existent task via MCP."""
        with pytest.raises(Exception):  # Should raise an error
            update_task.fn(
                task="NonExistentTask",
                new_code="df = pd.DataFrame()"
            )

    def test_delete_nonexistent_task(self, temp_dir):
        """Test deleting non-existent task via MCP."""
        with pytest.raises(Exception):  # Should raise an error
            delete_task.fn(task="NonExistentTask")