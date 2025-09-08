import pytest
import tempfile
import shutil
from pathlib import Path
from oryxforge.services.task_service import TaskService


@pytest.fixture
def temp_service():
    """Create a TaskService with temporary directory."""
    temp_dir = tempfile.mkdtemp()
    service = TaskService(base_dir=temp_dir)
    yield service
    shutil.rmtree(temp_dir)


class TestTaskServiceCore:
    """Core CRUD functionality tests."""
    
    def test_create_task(self, temp_service):
        """Test creating a new task."""
        temp_service.create("TestTask", "df = pd.DataFrame({'x': [1, 2, 3]})")
        
        # Check task was created
        tasks = temp_service.list_tasks()
        assert "TestTask" in tasks
        
        # Check code content
        code = temp_service.read("TestTask")
        assert "pd.DataFrame" in code
    
    def test_create_with_inputs(self, temp_service):
        """Test creating task with inputs."""
        temp_service.create("TaskA", "df = pd.DataFrame({'a': [1]})")
        temp_service.create("TaskB", "df = pd.DataFrame({'b': [2]})", inputs=["TaskA"])
        
        # Check both tasks exist
        tasks = temp_service.list_tasks()
        assert "TaskA" in tasks
        assert "TaskB" in tasks
    
    def test_create_duplicate_fails(self, temp_service):
        """Test creating duplicate task raises error."""
        temp_service.create("DupTask", "df = pd.DataFrame()")
        
        with pytest.raises(ValueError, match="already exists"):
            temp_service.create("DupTask", "df = pd.DataFrame()")
    
    def test_read_task(self, temp_service):
        """Test reading task code."""
        code = "df = pd.DataFrame({'test': [1, 2, 3]})"
        temp_service.create("ReadTask", code)
        
        read_code = temp_service.read("ReadTask")
        assert "pd.DataFrame" in read_code
        assert "test" in read_code
    
    def test_update_task(self, temp_service):
        """Test updating task code."""
        temp_service.create("UpdateTask", "df = pd.DataFrame({'old': [1]})")
        
        new_code = "df = pd.DataFrame({'new': [2]})"
        temp_service.update("UpdateTask", new_code=new_code)
        
        updated_code = temp_service.read("UpdateTask")
        assert "new" in updated_code
        assert "old" not in updated_code
    
    def test_delete_task(self, temp_service):
        """Test deleting a task."""
        temp_service.create("DeleteTask", "df = pd.DataFrame()")
        assert "DeleteTask" in temp_service.list_tasks()
        
        temp_service.delete("DeleteTask")
        assert "DeleteTask" not in temp_service.list_tasks()
    
    def test_upsert_create(self, temp_service):
        """Test upsert creates new task."""
        temp_service.upsert("NewTask", "df = pd.DataFrame({'new': [1]})")
        
        tasks = temp_service.list_tasks()
        assert "NewTask" in tasks
    
    def test_upsert_update(self, temp_service):
        """Test upsert updates existing task."""
        temp_service.create("ExistingTask", "df = pd.DataFrame({'old': [1]})")
        temp_service.upsert("ExistingTask", "df = pd.DataFrame({'updated': [2]})")
        
        code = temp_service.read("ExistingTask")
        assert "updated" in code
        assert "old" not in code


class TestTaskServiceModules:
    """Test module-specific functionality."""
    
    def test_create_in_module(self, temp_service):
        """Test creating task in specific module."""
        temp_service.create("ModuleTask", "df = pd.DataFrame()", module="test_module")
        
        # Check task in module
        tasks = temp_service.list_tasks("test_module")
        assert "ModuleTask" in tasks
        
        # Check not in default module
        default_tasks = temp_service.list_tasks()
        assert "ModuleTask" not in default_tasks
    
    def test_list_modules(self, temp_service):
        """Test listing available modules."""
        temp_service.create("Task1", "df = pd.DataFrame()", module="module_a")
        temp_service.create("Task2", "df = pd.DataFrame()", module="module_b")
        
        modules = temp_service.list_modules()
        assert "module_a" in modules
        assert "module_b" in modules


class TestTaskServiceNaming:
    """Test name sanitization functionality."""
    
    def test_sanitize_task_name(self, temp_service):
        """Test task name sanitization."""
        temp_service.create("invalid-name with spaces", "df = pd.DataFrame()")
        
        tasks = temp_service.list_tasks()
        # Should be converted to PascalCase
        assert any("Invalid" in task and "Name" in task for task in tasks)
    
    def test_sanitize_module_name(self, temp_service):
        """Test module name sanitization."""
        temp_service.create("TestTask", "df = pd.DataFrame()", module="Invalid-Module Name")
        
        modules = temp_service.list_modules()
        # Should be converted to snake_case
        assert any("invalid" in mod and "module" in mod for mod in modules)


class TestTaskServiceEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_read_nonexistent_task(self, temp_service):
        """Test reading non-existent task raises error."""
        with pytest.raises(ValueError, match="not found"):
            temp_service.read("NonExistentTask")
    
    def test_update_nonexistent_task(self, temp_service):
        """Test updating non-existent task raises error."""
        with pytest.raises(ValueError, match="not found"):
            temp_service.update("NonExistentTask", new_code="df = pd.DataFrame()")
    
    def test_delete_nonexistent_task(self, temp_service):
        """Test deleting non-existent task raises error."""
        with pytest.raises(ValueError, match="not found"):
            temp_service.delete("NonExistentTask")
    
    def test_empty_module_returns_empty_list(self, temp_service):
        """Test listing tasks from non-existent module."""
        tasks = temp_service.list_tasks("nonexistent_module")
        assert tasks == []


class TestTaskServiceDefaultModule:
    """Test default module (None) functionality."""
    
    def test_default_module_none(self, temp_service):
        """Test using default module (None uses __init__.py)."""
        # Create without specifying module (uses default None)
        temp_service.create("DefaultTask", "df = pd.DataFrame()")
        
        # Should be in default module
        tasks = temp_service.list_tasks()
        assert "DefaultTask" in tasks
        
        # Should be able to read
        code = temp_service.read("DefaultTask")
        assert "pd.DataFrame" in code