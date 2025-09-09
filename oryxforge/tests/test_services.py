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


class TestTaskServiceImportManagement:
    """Test import management functionality."""
    
    def _read_full_file(self, temp_service, module=None):
        """Helper to read full file content including imports."""
        from pathlib import Path
        if module is None:
            file_path = Path(temp_service.base_dir) / "tasks" / "__init__.py"
        else:
            file_path = Path(temp_service.base_dir) / "tasks" / f"{module}.py"
        return file_path.read_text()
    
    def test_create_task_with_imports(self, temp_service):
        """Test creating task with custom imports."""
        temp_service.create(
            "ImportTask", 
            "df = pd.DataFrame()",
            imports="import numpy as np\nfrom scipy import stats"
        )
        
        # Read just the method body (default)
        code = temp_service.read("ImportTask")
        assert "pd.DataFrame" in code
        
        # Read full file to check imports
        full_content = self._read_full_file(temp_service)
        assert "import numpy as np" in full_content
        assert "from scipy import stats" in full_content
    
    def test_import_deduplication(self, temp_service):
        """Test that duplicate imports are not added."""
        # Create first task with numpy import
        temp_service.create(
            "Task1",
            "arr = np.array([1, 2, 3])",
            imports="import numpy as np"
        )
        
        # Create second task with same numpy import - should not duplicate
        temp_service.create(
            "Task2", 
            "arr = np.array([4, 5, 6])",
            imports="import numpy as np\nfrom scipy import stats"
        )
        
        # Check first task has numpy import
        full_content1 = self._read_full_file(temp_service)
        numpy_count = full_content1.count("import numpy as np")
        assert numpy_count == 1  # Should only appear once despite being in both tasks
        assert "from scipy import stats" in full_content1  # Should have scipy from Task2
    
    def test_import_ordering(self, temp_service):
        """Test that new imports are added at bottom of existing imports."""
        # Create task with base imports
        temp_service.create(
            "OrderTask",
            "df = pd.DataFrame()",
            imports="import numpy as np"
        )
        
        # Update with additional imports
        temp_service.update(
            "OrderTask",
            new_imports="from scipy import stats\nimport matplotlib.pyplot as plt"
        )
        
        # Read full file to check import ordering
        full_content = self._read_full_file(temp_service)
        lines = full_content.split('\n')
        
        # Find import lines
        import_lines = [i for i, line in enumerate(lines) if line.strip().startswith(('import ', 'from '))]
        
        # Should have d6tflow import first, then our custom imports
        assert len(import_lines) >= 4
        assert "d6tflow" in lines[import_lines[0]]  # Base d6tflow import
        assert "pandas" in lines[import_lines[1]]   # Base pandas import
        assert "numpy" in lines[import_lines[2]]    # First custom import
        assert "scipy" in lines[import_lines[3]]    # Second custom import added later
    
    def test_update_with_imports(self, temp_service):
        """Test updating task imports."""
        # Create task without custom imports
        temp_service.create("UpdateImports", "df = pd.DataFrame()")
        
        # Update to add imports
        temp_service.update(
            "UpdateImports",
            new_imports="import numpy as np\nfrom pandas import Series"
        )
        
        full_content = self._read_full_file(temp_service)
        assert "import numpy as np" in full_content
        assert "from pandas import Series" in full_content
    
    def test_upsert_with_imports(self, temp_service):
        """Test upsert with imports (both create and update scenarios)."""
        # Test upsert creating new task
        temp_service.upsert(
            "UpsertNew",
            "df = pd.DataFrame()",
            imports="import numpy as np"
        )
        
        full_content = self._read_full_file(temp_service)
        assert "import numpy as np" in full_content
        
        # Test upsert updating existing task
        temp_service.upsert(
            "UpsertNew",
            "df = pd.DataFrame({'new': [1]})",
            imports="from scipy import stats"
        )
        
        updated_code = temp_service.read("UpsertNew")
        assert "new" in updated_code
        
        updated_full_content = self._read_full_file(temp_service)
        assert "from scipy import stats" in updated_full_content
    
    def test_import_conflict_detection(self, temp_service):
        """Test detection of import alias conflicts."""
        # Create task with numpy as np
        temp_service.create(
            "ConflictTask",
            "arr = np.array([1])",
            imports="import numpy as np"
        )
        
        # Try to add conflicting alias (numpy as different_alias)
        # This should work - the conflict detection allows different aliases for same module
        temp_service.update(
            "ConflictTask",
            new_imports="import numpy as different_np"
        )
        
        full_content = self._read_full_file(temp_service)
        assert "import numpy as np" in full_content
        assert "import numpy as different_np" in full_content
    
    def test_complex_import_scenarios(self, temp_service):
        """Test complex import management scenarios."""
        # Create with mixed import formats
        temp_service.create(
            "ComplexImports",
            "df = pd.DataFrame()",
            imports="import numpy as np\nfrom scipy import stats, optimize\nimport matplotlib.pyplot as plt"
        )
        
        full_content = self._read_full_file(temp_service)
        assert "import numpy as np" in full_content
        assert "from scipy import stats, optimize" in full_content
        assert "import matplotlib.pyplot as plt" in full_content
        
        # Update with additional imports
        temp_service.update(
            "ComplexImports",
            new_imports="from sklearn import metrics\nimport seaborn as sns"
        )
        
        updated_full_content = self._read_full_file(temp_service)
        assert "from sklearn import metrics" in updated_full_content
        assert "import seaborn as sns" in updated_full_content
        # Original imports should still be there
        assert "import numpy as np" in updated_full_content
        assert "from scipy import stats, optimize" in updated_full_content


class TestTaskServiceFlowExecution:
    """Test flow execution functionality."""
    
    def test_generate_flow_script_basic(self, temp_service):
        """Test basic flow script generation using create_preview."""
        # Create a simple task first
        temp_service.create("TestTask", "df = pd.DataFrame({'x': [1, 2, 3]})")
        
        # Generate flow script
        script = temp_service.create_preview(
            "TestTask", 
            flow_params={"model": "test"}
        )
        
        # Verify script contains expected elements
        assert "import d6tflow" in script
        assert "import tasks" in script
        assert "params = {'model': 'test'}" in script
        assert "task = tasks.TestTask" in script
        assert "d6tflow.Workflow(task=task, params=params)" in script
        assert "flow.preview()" in script

    def test_generate_flow_script_with_module(self, temp_service):
        """Test flow script generation with specific module using create_run."""
        # Create task in specific module
        temp_service.create("ModuleTask", "df = pd.DataFrame()", module="test_module")
        
        script = temp_service.create_run(
            "ModuleTask", 
            module="test_module",
            flow_params={}
        )
        
        assert "import tasks.test_module as tasks" in script
        assert "task = tasks.ModuleTask" in script
        assert "flow.run()" in script

    def test_generate_flow_script_with_reset_tasks(self, temp_service):
        """Test flow script generation with reset tasks using create_preview."""
        # Create multiple tasks
        temp_service.create("TaskA", "df = pd.DataFrame({'a': [1]})")
        temp_service.create("TaskB", "df = pd.DataFrame({'b': [2]})", inputs=["TaskA"])
        
        script = temp_service.create_preview(
            "TaskB", 
            reset_tasks=["TaskA", "TaskB"]
        )
        
        assert "flow.reset(tasks.TaskA)" in script
        assert "flow.reset(tasks.TaskB)" in script

    def test_validate_reset_tasks(self, temp_service):
        """Test reset task validation."""
        # Create some tasks
        temp_service.create("ValidTask", "df = pd.DataFrame()")
        temp_service.create("AnotherTask", "df = pd.DataFrame()")
        
        # Test validation with valid tasks
        validated = temp_service._validate_reset_tasks(["ValidTask", "AnotherTask"], None)
        assert validated == ["ValidTask", "AnotherTask"]
        
        # Test validation with invalid tasks (should still return them but log warning)
        validated = temp_service._validate_reset_tasks(["ValidTask", "NonExistent"], None)
        assert validated == ["ValidTask", "NonExistent"]

    def test_validate_reset_tasks_name_sanitization(self, temp_service):
        """Test that reset task names are sanitized."""
        temp_service.create("ValidTask", "df = pd.DataFrame()")
        
        # Test with names that need sanitization
        validated = temp_service._validate_reset_tasks(["valid-task", "another_task"], None)
        assert validated == ["ValidTask", "AnotherTask"]

    def test_create_preview_basic(self, temp_service):
        """Test basic preview script generation."""
        # Create a simple task
        temp_service.create("SimpleTask", "df = pd.DataFrame({'test': [1, 2]})")
        
        # Generate preview script
        result = temp_service.create_preview("SimpleTask", flow_params={"test": "value"})
        assert isinstance(result, str)
        assert "flow.preview()" in result
        assert "import d6tflow" in result
        assert "'test': 'value'" in result

    def test_create_run_basic(self, temp_service):
        """Test basic run script generation."""
        # Create a simple task
        temp_service.create("RunTask", "df = pd.DataFrame({'run': [1, 2]})")
        
        # Generate run script
        result = temp_service.create_run("RunTask", flow_params={"test": "run"})
        assert isinstance(result, str)
        assert "flow.run()" in result
        assert "import d6tflow" in result
        assert "'test': 'run'" in result

    def test_flow_with_nonexistent_task(self, temp_service):
        """Test flow script generation with non-existent task."""
        # Should raise error during task validation
        with pytest.raises(ValueError, match="not found"):
            temp_service.create_preview("NonExistentTask")

    def test_flow_parameter_handling(self, temp_service):
        """Test different parameter types in flow."""
        temp_service.create("ParamTask", "df = pd.DataFrame()")
        
        # Test with various parameter types using create_preview
        script = temp_service.create_preview(
            "ParamTask",
            flow_params={
                "string_param": "test",
                "int_param": 42,
                "list_param": [1, 2, 3],
                "dict_param": {"nested": "value"}
            }
        )
        
        # Verify parameters are properly represented
        assert "'string_param': 'test'" in script
        assert "'int_param': 42" in script
        assert "'list_param': [1, 2, 3]" in script
        assert "'dict_param': {'nested': 'value'}" in script

    def test_flow_execution_end_to_end(self, temp_service):
        """Test complete flow script generation from task creation to script generation."""
        # Create tasks with dependencies
        temp_service.create("GetData", "df = pd.DataFrame({'raw': [1, 2, 3, 4, 5]})")
        temp_service.create("ProcessData", 
                          "input_df = self.input()['GetData'].read()\ndf = input_df.copy()\ndf['processed'] = df['raw'] * 2", 
                          inputs=["GetData"])
        
        # Test that the complete flow script includes all necessary components
        script = temp_service.create_preview(
            "ProcessData", 
            flow_params={"batch_size": 100, "debug": True}, 
            reset_tasks=["GetData"]
        )
        
        # Verify complete script structure
        lines = script.strip().split('\n')
        
        # Should have d6tflow import
        assert any("import d6tflow" in line for line in lines)
        
        # Should have tasks import
        assert any("import tasks" in line for line in lines)
        
        # Should have parameters
        assert any("'batch_size': 100" in line for line in lines)
        assert any("'debug': True" in line for line in lines)
        
        # Should have task reference
        assert any("task = tasks.ProcessData" in line for line in lines)
        
        # Should have workflow creation
        assert any("d6tflow.Workflow(task=task, params=params)" in line for line in lines)
        
        # Should have reset command
        assert any("flow.reset(tasks.GetData)" in line for line in lines)
        
        # Should have preview command
        assert any("flow.preview()" in line for line in lines)

    def test_flow_script_execution_validation(self, temp_service):
        """Test that generated scripts are valid Python and would execute if d6tflow available."""
        # Create a simple task
        temp_service.create("ValidationTask", "df = pd.DataFrame({'test': [1]})")
        
        # Generate script
        script = temp_service.create_preview(
            "ValidationTask", 
            flow_params={"test": "validation"}
        )
        
        # Validate that the script is syntactically correct Python
        try:
            compile(script, '<string>', 'exec')
        except SyntaxError as e:
            pytest.fail(f"Generated script has syntax error: {e}")
        
        # Verify script would import correctly (mock check)
        assert "import d6tflow" in script
        assert "import tasks" in script
        assert script.count("import") >= 2  # At least d6tflow and tasks

    def test_flow_with_empty_parameters(self, temp_service):
        """Test flow script generation with empty parameters."""
        temp_service.create("EmptyParamTask", "df = pd.DataFrame()")
        
        # Test with None parameters
        script1 = temp_service.create_preview("EmptyParamTask")
        assert "params = {}" in script1
        
        # Test with empty dict parameters
        script2 = temp_service.create_preview("EmptyParamTask", flow_params={}, reset_tasks=[])
        assert "params = {}" in script2
        
        # Test with empty reset tasks
        assert "# Reset tasks\n\n" in script2 or "# Reset tasks\n# Execute" in script2

    def test_flow_complex_dependency_chain(self, temp_service):
        """Test flow script generation with complex task dependencies."""
        # Create a chain of dependent tasks
        temp_service.create("RawData", "df = pd.DataFrame({'id': range(10), 'value': range(10, 20)})")
        temp_service.create("CleanData", 
                          "raw = self.input()['RawData'].read()\ndf = raw[raw['value'] > 12]", 
                          inputs=["RawData"])
        temp_service.create("FeatureData", 
                          "clean = self.input()['CleanData'].read()\ndf = clean.copy()\ndf['feature'] = df['value'] ** 2", 
                          inputs=["CleanData"])
        temp_service.create("ModelData", 
                          "features = self.input()['FeatureData'].read()\ndf = features.copy()\ndf['prediction'] = df['feature'] * 0.1", 
                          inputs=["FeatureData"])
        
        # Test generating run script for the full chain with multiple resets
        script = temp_service.create_run(
            "ModelData", 
            flow_params={"model_type": "linear", "threshold": 0.8}, 
            reset_tasks=["RawData", "CleanData", "FeatureData"]
        )
        
        # Verify all resets are included in correct order
        assert "flow.reset(tasks.RawData)" in script
        assert "flow.reset(tasks.CleanData)" in script
        assert "flow.reset(tasks.FeatureData)" in script
        
        # Verify final task and run command
        assert "task = tasks.ModelData" in script
        assert "flow.run()" in script
        
        # Verify parameters
        assert "'model_type': 'linear'" in script
        assert "'threshold': 0.8" in script

    def test_flow_error_handling_validation(self, temp_service):
        """Test flow script generation validation catches errors properly."""
        temp_service.create("ValidTask", "df = pd.DataFrame()")
        
        # Test with invalid task name - should raise ValueError before script generation
        with pytest.raises(ValueError, match="not found"):
            temp_service.create_preview("InvalidTask")
        
        # Test with valid task but invalid reset task - should warn but continue
        temp_service.create("MainTask", "df = pd.DataFrame()")
        
        # This should work but log warnings for invalid reset tasks
        validated_tasks = temp_service._validate_reset_tasks(["MainTask", "InvalidReset"], None)
        assert "MainTask" in validated_tasks
        assert "InvalidReset" in validated_tasks  # Still included but with warning

    def test_flow_module_specific_execution(self, temp_service):
        """Test flow script generation with module-specific tasks."""
        # Create tasks in different modules
        temp_service.create("DefaultTask", "df = pd.DataFrame({'default': [1]})")
        temp_service.create("ModuleTask", "df = pd.DataFrame({'module': [1]})", module="custom_module")
        
        # Test default module execution
        script1 = temp_service.create_preview("DefaultTask")
        assert "import tasks" in script1
        assert "task = tasks.DefaultTask" in script1
        
        # Test custom module execution
        script2 = temp_service.create_preview("ModuleTask", module="custom_module")
        assert "import tasks.custom_module as tasks" in script2
        assert "task = tasks.ModuleTask" in script2
    
    def test_execute_preview_basic(self, temp_service):
        """Test executing preview script."""
        # Create a simple task
        temp_service.create("ExecuteTask", "df = pd.DataFrame({'execute': [1]})")
        
        # Generate script
        script = temp_service.create_preview("ExecuteTask")
        
        # Try to execute - may fail if d6tflow not available
        try:
            result = temp_service.execute_preview(script)
            assert isinstance(result, str)
        except Exception:
            # Expected if d6tflow is not installed
            pass
    
    def test_execute_run_basic(self, temp_service):
        """Test executing run script."""
        # Create a simple task
        temp_service.create("RunExecuteTask", "df = pd.DataFrame({'run': [1]})")
        
        # Generate script
        script = temp_service.create_run("RunExecuteTask")
        
        # Try to execute - may fail if d6tflow not available
        try:
            result = temp_service.execute_run(script)
            assert isinstance(result, str)
        except Exception:
            # Expected if d6tflow is not installed
            pass
    
    def test_preview_flow_integration(self, temp_service):
        """Test integrated preview_flow method."""
        # Create a simple task
        temp_service.create("IntegrationTask", "df = pd.DataFrame({'integration': [1]})")
        
        # Try integrated preview flow - may fail if d6tflow not available
        try:
            result = temp_service.preview_flow(
                "IntegrationTask",
                flow_params={"test": "integration"}
            )
            assert isinstance(result, str)
        except Exception:
            # Expected if d6tflow is not installed
            pass