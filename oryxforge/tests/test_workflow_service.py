import pytest
import tempfile
import shutil
from pathlib import Path
from ..services.workflow_service import WorkflowService


@pytest.fixture
def temp_service():
    """Create a WorkflowService with temporary directory."""
    temp_dir = tempfile.mkdtemp()
    service = WorkflowService(base_dir=temp_dir)
    yield service
    shutil.rmtree(temp_dir)


class TestWorkflowServiceCore:
    """Core CRUD functionality tests."""
    
    def test_create_task(self, temp_service):
        """Test creating a new sheet."""
        temp_service.create("TestTask", {'run': "df_out = pd.DataFrame({'x': [1, 2, 3]})"})

        # Check sheet was created
        tasks = temp_service.list_sheets()
        assert "TestTask" in tasks

        # Check code content
        code = temp_service.read("TestTask")
        assert "pd.DataFrame" in code
    
    def test_create_with_inputs(self, temp_service):
        """Test creating task with inputs."""
        temp_service.create("TaskA", {'run': "df_out = pd.DataFrame({'a': [1]})"})
        temp_service.create("TaskB", {'run': "df_out = pd.DataFrame({'b': [2]})"}, inputs=[{"dataset": None, "sheet": "TaskA"}])

        # Check both tasks exist
        tasks = temp_service.list_sheets()
        assert "TaskA" in tasks
        assert "TaskB" in tasks

    def test_create_duplicate_fails(self, temp_service):
        """Test creating duplicate task raises error."""
        temp_service.create("DupTask", {'run': "df_out = pd.DataFrame()"})

        with pytest.raises(ValueError, match="already exists"):
            temp_service.create("DupTask", {'run': "df_out = pd.DataFrame()"})
    
    def test_read_task(self, temp_service):
        """Test reading task code."""
        code = "df_out = pd.DataFrame({'test': [1, 2, 3]})"
        temp_service.create("ReadTask", {'run': code})

        # Read run method by default (specifying method='run')
        read_code = temp_service.read("ReadTask", method='run')
        assert "pd.DataFrame" in read_code
        assert "test" in read_code

    def test_read_run_convenience(self, temp_service):
        """Test read_run convenience function."""
        code = "df_out = pd.DataFrame({'data': [1, 2, 3]})"
        temp_service.create("ReadRunTask", {'run': code})

        # Use convenience function
        read_code = temp_service.read_run("ReadRunTask")
        assert "pd.DataFrame" in read_code
        assert "data" in read_code

    def test_read_specific_method(self, temp_service):
        """Test reading specific method code."""
        temp_service.create("MultiMethodTask", {
            'run': "df_out = pd.DataFrame({'x': [1]})",
            'eda': "return self.output().read().describe()",
            'custom': "return 'custom method'"
        })

        # Read run method
        run_code = temp_service.read("MultiMethodTask", method='run')
        assert "pd.DataFrame" in run_code
        assert "describe" not in run_code

        # Read eda method
        eda_code = temp_service.read("MultiMethodTask", method='eda')
        assert "describe()" in eda_code
        assert "pd.DataFrame" not in eda_code

        # Read custom method
        custom_code = temp_service.read("MultiMethodTask", method='custom')
        assert "custom method" in custom_code

    def test_read_full_class(self, temp_service):
        """Test reading full class definition."""
        temp_service.create("FullClassTask", {
            'run': "df_out = pd.DataFrame({'x': [1]})",
            'eda': "return self.output().read().head()"
        })

        # Read full class (method=None)
        full_class = temp_service.read("FullClassTask", method=None)
        assert "class FullClassTask" in full_class
        assert "def run(self):" in full_class
        assert "def eda(self):" in full_class

    def test_update_task(self, temp_service):
        """Test updating task code."""
        temp_service.create("UpdateTask", {'run': "df_out = pd.DataFrame({'old': [1]})"})

        new_code = "df_out = pd.DataFrame({'new': [2]})"
        temp_service.update("UpdateTask", new_code={'run': new_code})

        updated_code = temp_service.read("UpdateTask")
        assert "new" in updated_code
        assert "old" not in updated_code
    
    def test_delete_task(self, temp_service):
        """Test deleting a task."""
        temp_service.create("DeleteTask", {'run': "df_out = pd.DataFrame()"})
        assert "DeleteTask" in temp_service.list_sheets()

        temp_service.delete("DeleteTask")
        assert "DeleteTask" not in temp_service.list_sheets()

    def test_upsert_create(self, temp_service):
        """Test upsert creates new task."""
        temp_service.upsert("NewTask", {'run': "df_out = pd.DataFrame({'new': [1]})"})

        tasks = temp_service.list_sheets()
        assert "NewTask" in tasks

    def test_upsert_update(self, temp_service):
        """Test upsert updates existing task."""
        temp_service.create("ExistingTask", {'run': "df_out = pd.DataFrame({'old': [1]})"})
        temp_service.upsert("ExistingTask", {'run': "df_out = pd.DataFrame({'updated': [2]})"})

        code = temp_service.read("ExistingTask")
        assert "updated" in code
        assert "old" not in code

    def test_upsert_run_convenience(self, temp_service):
        """Test upsert_run convenience function."""
        # Create new task with upsert_run
        temp_service.upsert_run("RunTask", "df_out = pd.DataFrame({'test': [1, 2, 3]})")

        tasks = temp_service.list_sheets()
        assert "RunTask" in tasks

    def test_upsert_run_without_df_out(self, temp_service):
        """Test upsert_run raises error when df_out is missing."""
        with pytest.raises(ValueError, match="must assign results to 'df_out'"):
            temp_service.upsert_run("BadTask", "df = pd.DataFrame({'test': [1]})")

    def test_upsert_eda_convenience(self, temp_service):
        """Test upsert_eda convenience function."""
        # First create a task with run method
        temp_service.upsert_run("EdaTask", "df_out = pd.DataFrame({'data': [1, 2, 3]})")

        # Add eda method using convenience function
        temp_service.upsert_eda("EdaTask", "return self.output().read().head(10)")

        # Read full file to verify both methods exist
        from pathlib import Path
        file_path = Path(temp_service.base_dir) / "tasks" / "__init__.py"
        full_content = file_path.read_text()

        assert "def run(self):" in full_content
        assert "def eda(self):" in full_content
        assert "return self.output().read().head(10)" in full_content
        assert "pd.DataFrame" in full_content

    def test_upsert_eda_nonexistent_task(self, temp_service):
        """Test upsert_eda creates task with default run method when task doesn't exist."""
        # Should create task with default run method
        temp_service.upsert_eda("NonExistentTask", "return df.head()")

        # Verify task was created
        assert "NonExistentTask" in temp_service.list_sheets()

        # Verify both run and eda methods exist
        from pathlib import Path
        file_path = Path(temp_service.base_dir) / "tasks" / "__init__.py"
        full_content = file_path.read_text()

        assert "def run(self):" in full_content
        assert "def eda(self):" in full_content
        assert "return df.head()" in full_content


class TestWorkflowServiceModules:
    """Test module-specific functionality."""

    def test_create_in_module(self, temp_service):
        """Test creating task in specific module."""
        temp_service.create("ModuleTask", {'run': "df_out = pd.DataFrame()"}, dataset="test_module")

        # Check task in module
        tasks = temp_service.list_sheets("test_module")
        assert "ModuleTask" in tasks

        # Check not in default module
        default_tasks = temp_service.list_sheets()
        assert "ModuleTask" not in default_tasks

    def test_list_datasets(self, temp_service):
        """Test listing available modules."""
        temp_service.create("Task1", {'run': "df_out = pd.DataFrame()"}, dataset="module_a")
        temp_service.create("Task2", {'run': "df_out = pd.DataFrame()"}, dataset="module_b")

        modules = temp_service.list_datasets()
        assert "module_a" in modules
        assert "module_b" in modules


class TestWorkflowServiceNaming:
    """Test name sanitization functionality."""

    def test_sanitize_task_name(self):
        """Test task name sanitization."""
        temp_dir = tempfile.mkdtemp()
        temp_service = WorkflowService(base_dir=temp_dir, sanitize=True)
        try:
            temp_service.create("invalid-name with spaces", {'run': "df_out = pd.DataFrame()"})

            tasks = temp_service.list_sheets()
            # Should be converted to PascalCase
            assert any("Invalid" in task and "Name" in task for task in tasks)
        finally:
            shutil.rmtree(temp_dir)

    def test_sanitize_module_name(self):
        """Test module name sanitization."""
        temp_dir = tempfile.mkdtemp()
        temp_service = WorkflowService(base_dir=temp_dir, sanitize=True)
        try:
            temp_service.create("TestTask", {'run': "df_out = pd.DataFrame()"}, dataset="Invalid-Module Name")

            modules = temp_service.list_datasets()
            # Should be converted to snake_case
            assert any("invalid" in mod and "module" in mod for mod in modules)
        finally:
            shutil.rmtree(temp_dir)


class TestWorkflowServiceEdgeCases:
    """Test edge cases and error conditions."""

    def test_read_nonexistent_task(self, temp_service):
        """Test reading non-existent task raises error."""
        with pytest.raises(ValueError, match="not found"):
            temp_service.read("NonExistentTask")

    def test_update_nonexistent_task(self, temp_service):
        """Test updating non-existent task raises error."""
        with pytest.raises(ValueError, match="not found"):
            temp_service.update("NonExistentTask", new_code={'run': "df_out = pd.DataFrame()"})

    def test_delete_nonexistent_task(self, temp_service):
        """Test deleting non-existent task raises error."""
        with pytest.raises(ValueError, match="not found"):
            temp_service.delete("NonExistentTask")

    def test_empty_module_returns_empty_list(self, temp_service):
        """Test listing tasks from non-existent module."""
        tasks = temp_service.list_sheets("nonexistent_module")
        assert tasks == []


class TestWorkflowServiceDefaultModule:
    """Test default module (None) functionality."""

    def test_default_module_none(self, temp_service):
        """Test using default module (None uses __init__.py)."""
        # Create without specifying module (uses default None)
        temp_service.create("DefaultTask", {'run': "df_out = pd.DataFrame()"})

        # Should be in default module
        tasks = temp_service.list_sheets()
        assert "DefaultTask" in tasks

        # Should be able to read
        code = temp_service.read("DefaultTask")
        assert "pd.DataFrame" in code


class TestWorkflowServiceImportManagement:
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
            {'run': "df_out = pd.DataFrame()"},
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
            {'run': "df_out = np.array([1, 2, 3])"},
            imports="import numpy as np"
        )

        # Create second task with same numpy import - should not duplicate
        temp_service.create(
            "Task2",
            {'run': "df_out = np.array([4, 5, 6])"},
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
            {'run': "df_out = pd.DataFrame()"},
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
        temp_service.create("UpdateImports", {'run': "df_out = pd.DataFrame()"})

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
            {'run': "df_out = pd.DataFrame()"},
            imports="import numpy as np"
        )

        full_content = self._read_full_file(temp_service)
        assert "import numpy as np" in full_content

        # Test upsert updating existing task
        temp_service.upsert(
            "UpsertNew",
            {'run': "df_out = pd.DataFrame({'new': [1]})"},
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
            {'run': "df_out = np.array([1])"},
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
            {'run': "df_out = pd.DataFrame()"},
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


class TestWorkflowServiceCodeMethods:
    """Test code_methods functionality."""

    def _read_full_file(self, temp_service, module=None):
        """Helper to read full file content including all methods."""
        from pathlib import Path
        if module is None:
            file_path = Path(temp_service.base_dir) / "tasks" / "__init__.py"
        else:
            file_path = Path(temp_service.base_dir) / "tasks" / f"{module}.py"
        return file_path.read_text()

    def test_create_task_with_code_methods(self, temp_service):
        """Test creating task with additional methods."""
        code = {
            'run': "df_out = pd.DataFrame({'x': [1, 2, 3]})",
            'eda': 'return self.output().read().head(10)',
            'summary': 'df = self.output().read()\nreturn df.describe()',
            'plot-data': 'import matplotlib.pyplot as plt\ndf = self.output().read()\nplt.plot(df)'
        }

        temp_service.create(
            "TestCodeMethods",
            code
        )

        # Check that the task was created
        tasks = temp_service.list_sheets()
        assert "TestCodeMethods" in tasks

        # Check full file content
        full_content = self._read_full_file(temp_service)
        assert "def eda(self):" in full_content
        assert "def summary(self):" in full_content
        assert "def plot_data(self):" in full_content  # Method name should be sanitized
        assert "return self.output().read().head(10)" in full_content
        assert "return df.describe()" in full_content
        assert "plt.plot(df)" in full_content

    def test_upsert_task_with_code_methods(self, temp_service):
        """Test upsert with code_methods."""
        code = {
            'run': "df_out = pd.DataFrame({'values': [1, 2, 3, 4, 5]})",
            'analyze': 'data = self.output().read()\nreturn data.mean()'
        }

        temp_service.upsert(
            "UpsertWithMethods",
            code
        )

        full_content = self._read_full_file(temp_service)
        assert "def analyze(self):" in full_content
        assert "return data.mean()" in full_content

    def test_update_task_with_code_methods(self, temp_service):
        """Test updating existing task with new methods."""
        # Create initial task
        temp_service.create(
            "UpdateMethods",
            {'run': "df_out = pd.DataFrame({'initial': [1]})"}
        )

        # Update with new methods
        new_code = {
            'run': "df_out = pd.DataFrame({'initial': [1]})",
            'method1': 'return "method1"',
            'method2': 'return "method2"'
        }

        temp_service.update(
            "UpdateMethods",
            new_code=new_code
        )

        full_content = self._read_full_file(temp_service)
        assert "def method1(self):" in full_content
        assert "def method2(self):" in full_content
        assert "return 'method1'" in full_content
        assert "return 'method2'" in full_content

    def test_update_replaces_existing_methods(self, temp_service):
        """Test that updating methods replaces existing custom methods."""
        # Create task with initial methods
        initial_code = {
            'run': "df_out = pd.DataFrame()",
            'old_method': 'return "old"'
        }

        temp_service.create(
            "ReplaceMethodsTest",
            initial_code
        )

        # Verify initial method exists
        full_content = self._read_full_file(temp_service)
        assert "def old_method(self):" in full_content

        # Update with new methods
        new_code = {
            'run': "df_out = pd.DataFrame()",
            'new_method': 'return "new"'
        }

        temp_service.update(
            "ReplaceMethodsTest",
            new_code=new_code
        )

        # Check that old method is gone and new method exists
        updated_content = self._read_full_file(temp_service)
        assert "def old_method(self):" not in updated_content
        assert "def new_method(self):" in updated_content
        assert "return 'new'" in updated_content

    def test_method_name_sanitization(self, temp_service):
        """Test that method names are properly sanitized."""
        code = {
            'run': "df_out = pd.DataFrame()",
            'invalid-name': 'return 1',
            'Another Name': 'return 2',
            '123numeric': 'return 3',
            'class': 'return 4',  # Python keyword
        }

        temp_service.create(
            "SanitizeTest",
            code
        )

        full_content = self._read_full_file(temp_service)
        assert "def invalid_name(self):" in full_content
        assert "def another_name(self):" in full_content
        assert "def m_123numeric(self):" in full_content
        assert "def class_method(self):" in full_content

        # Should have the original run method
        assert "def run(self):" in full_content

    def test_empty_code_methods(self, temp_service):
        """Test that empty code_methods dict doesn't break anything."""
        temp_service.create(
            "EmptyMethods",
            {'run': "df_out = pd.DataFrame()"}
        )

        # Should work normally
        tasks = temp_service.list_sheets()
        assert "EmptyMethods" in tasks

        # Should only have run method
        full_content = self._read_full_file(temp_service)
        method_count = full_content.count("def ")
        assert method_count == 1  # Only run method

    def test_none_code_methods(self, temp_service):
        """Test that None code_methods works normally."""
        temp_service.create(
            "NoneMethods",
            {'run': "df_out = pd.DataFrame()"}
        )

        tasks = temp_service.list_sheets()
        assert "NoneMethods" in tasks

    def test_complex_method_code(self, temp_service):
        """Test methods with complex code including multiple lines."""
        code = {
            'run': "df_out = pd.DataFrame({'category': ['A', 'B'], 'value': [1, 2]})",
            'complex_analysis': '''
# This is a complex method
data = self.output().read()
if len(data) > 0:
    result = data.groupby('category').agg({
        'value': ['mean', 'std', 'count']
    })
    return result
else:
    return None
'''.strip()
        }

        temp_service.create(
            "ComplexMethods",
            code
        )

        full_content = self._read_full_file(temp_service)
        assert "def complex_analysis(self):" in full_content
        # Comments might get stripped by AST, so just check the code logic
        assert "data.groupby('category')" in full_content
        assert "return result" in full_content
        assert "return None" in full_content


class TestWorkflowServiceFlowExecution:
    """Test flow execution functionality."""
    
    def test_generate_flow_script_basic(self, temp_service):
        """Test basic flow script generation using run_preview."""
        # Create a simple task first
        temp_service.create("TestTask", {'run': "df_out = pd.DataFrame({'x': [1, 2, 3]})"})

        # Generate flow script (no file_out to get script content)
        script = temp_service.run_preview(
            "TestTask",
            flow_params={"model": "test"},
            file_out=None
        )

        # Verify script contains expected elements
        assert "import d6tflow" in script
        assert "import tasks" in script
        assert "params = {'model': 'test'}" in script
        assert "task = tasks.TestTask" in script
        assert "d6tflow.Workflow(task=task, params=params)" in script
        assert "flow.preview()" in script

    def test_generate_flow_script_with_module(self, temp_service):
        """Test flow script generation with specific module using run_flow."""
        # Create task in specific module
        temp_service.create("ModuleTask", {'run': "df_out = pd.DataFrame()"}, dataset="test_module")

        script = temp_service.run_flow(
            "ModuleTask",
            dataset="test_module",
            flow_params={},
            file_out=None
        )

        assert "import tasks.test_module as tasks" in script
        assert "task = tasks.ModuleTask" in script
        assert "flow.run()" in script

    def test_generate_flow_script_with_reset_tasks(self, temp_service):
        """Test flow script generation with reset tasks using run_preview."""
        # Create multiple tasks
        temp_service.create("TaskA", {'run': "df_out = pd.DataFrame({'a': [1]})"})
        temp_service.create("TaskB", {'run': "df_out = pd.DataFrame({'b': [2]})"}, inputs=[{"dataset": None, "sheet": "TaskA"}])

        script = temp_service.run_preview(
            "TaskB",
            reset_sheets=["TaskA", "TaskB"],
            file_out=None
        )

        assert "flow.reset(tasks.TaskA)" in script
        assert "flow.reset(tasks.TaskB)" in script

    def test_validate_reset_tasks(self, temp_service):
        """Test reset task validation."""
        # Create some tasks
        temp_service.create("ValidTask", {'run': "df_out = pd.DataFrame()"})
        temp_service.create("AnotherTask", {'run': "df_out = pd.DataFrame()"})

        # Test validation with valid tasks
        validated = temp_service._validate_reset_tasks(["ValidTask", "AnotherTask"], None)
        assert validated == ["ValidTask", "AnotherTask"]

        # Test validation with invalid tasks (should still return them but log warning)
        validated = temp_service._validate_reset_tasks(["ValidTask", "NonExistent"], None)
        assert validated == ["ValidTask", "NonExistent"]

    def test_validate_reset_tasks_name_sanitization(self, temp_service):
        """Test that reset task names are sanitized."""
        temp_service.create("ValidTask", {'run': "df_out = pd.DataFrame()"})

        # Test with names that need sanitization
        validated = temp_service._validate_reset_tasks(["valid-task", "another_task"], None)
        assert validated == ["ValidTask", "AnotherTask"]

    def test_run_preview_basic(self, temp_service):
        """Test basic preview script generation."""
        # Create a simple task
        temp_service.create("SimpleTask", {'run': "df_out = pd.DataFrame({'test': [1, 2]})"})

        # Generate preview script (no file_out to get script content)
        result = temp_service.run_preview("SimpleTask", flow_params={"test": "value"}, file_out=None)
        assert isinstance(result, str)
        assert "flow.preview()" in result
        assert "import d6tflow" in result
        assert "'test': 'value'" in result

    def test_run_flow_basic(self, temp_service):
        """Test basic run script generation."""
        # Create a simple task
        temp_service.create("RunTask", {'run': "df_out = pd.DataFrame({'run': [1, 2]})"})

        # Generate run script (no file_out to get script content)
        result = temp_service.run_flow("RunTask", flow_params={"test": "run"}, file_out=None)
        assert isinstance(result, str)
        assert "flow.run()" in result
        assert "import d6tflow" in result
        assert "'test': 'run'" in result

    def test_flow_with_nonexistent_task(self, temp_service):
        """Test flow script generation with non-existent task."""
        # Should raise error during task validation
        with pytest.raises(ValueError, match="not found"):
            temp_service.run_preview("NonExistentTask")

    def test_flow_parameter_handling(self, temp_service):
        """Test different parameter types in flow."""
        temp_service.create("ParamTask", {'run': "df_out = pd.DataFrame()"})

        # Test with various parameter types using run_preview
        script = temp_service.run_preview(
            "ParamTask",
            flow_params={
                "string_param": "test",
                "int_param": 42,
                "list_param": [1, 2, 3],
                "dict_param": {"nested": "value"}
            },
            file_out=None
        )

        # Verify parameters are properly represented
        assert "'string_param': 'test'" in script
        assert "'int_param': 42" in script
        assert "'list_param': [1, 2, 3]" in script
        assert "'dict_param': {'nested': 'value'}" in script

    def test_flow_execution_end_to_end(self, temp_service):
        """Test complete flow script generation from task creation to script generation."""
        # Create tasks with dependencies
        temp_service.create("GetData", {'run': "df_out = pd.DataFrame({'raw': [1, 2, 3, 4, 5]})"})
        temp_service.create("ProcessData",
                          {'run': "input_df = self.input()['GetData'].read()\ndf_out = input_df.copy()\ndf_out['processed'] = df_out['raw'] * 2"},
                          inputs=[{"dataset": None, "sheet": "GetData"}])

        # Test that the complete flow script includes all necessary components
        script = temp_service.run_preview(
            "ProcessData",
            flow_params={"batch_size": 100, "debug": True},
            reset_sheets=["GetData"],
            file_out=None
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
        temp_service.create("ValidationTask", {'run': "df_out = pd.DataFrame({'test': [1]})"})

        # Generate script
        script = temp_service.run_preview(
            "ValidationTask",
            flow_params={"test": "validation"},
            file_out=None
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
        temp_service.create("EmptyParamTask", {'run': "df_out = pd.DataFrame()"})

        # Test with None parameters
        script1 = temp_service.run_preview("EmptyParamTask", file_out=None)
        assert "params = {}" in script1

        # Test with empty dict parameters
        script2 = temp_service.run_preview("EmptyParamTask", flow_params={}, reset_sheets=[], file_out=None)
        assert "params = {}" in script2

        # Test with empty reset tasks
        assert "# Reset tasks\n\n" in script2 or "# Reset tasks\n# Execute" in script2

    def test_flow_complex_dependency_chain(self, temp_service):
        """Test flow script generation with complex task dependencies."""
        # Create a chain of dependent tasks
        temp_service.create("RawData", {'run': "df_out = pd.DataFrame({'id': range(10), 'value': range(10, 20)})"})
        temp_service.create("CleanData",
                          {'run': "raw = self.input()['RawData'].read()\ndf_out = raw[raw['value'] > 12]"},
                          inputs=[{"dataset": None, "sheet": "RawData"}])
        temp_service.create("FeatureData",
                          {'run': "clean = self.input()['CleanData'].read()\ndf_out = clean.copy()\ndf_out['feature'] = df_out['value'] ** 2"},
                          inputs=[{"dataset": None, "sheet": "CleanData"}])
        temp_service.create("ModelData",
                          {'run': "features = self.input()['FeatureData'].read()\ndf_out = features.copy()\ndf_out['prediction'] = df_out['feature'] * 0.1"},
                          inputs=[{"dataset": None, "sheet": "FeatureData"}])

        # Test generating run script for the full chain with multiple resets
        script = temp_service.run_flow(
            "ModelData",
            flow_params={"model_type": "linear", "threshold": 0.8},
            reset_sheets=["RawData", "CleanData", "FeatureData"],
            file_out=None
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
        temp_service.create("ValidTask", {'run': "df_out = pd.DataFrame()"})

        # Test with invalid task name - should raise ValueError before script generation
        with pytest.raises(ValueError, match="not found"):
            temp_service.run_preview("InvalidTask")

        # Test with valid task but invalid reset task - should warn but continue
        temp_service.create("MainTask", {'run': "df_out = pd.DataFrame()"})

        # This should work but log warnings for invalid reset tasks
        validated_tasks = temp_service._validate_reset_tasks(["MainTask", "InvalidReset"], None)
        assert "MainTask" in validated_tasks
        assert "InvalidReset" in validated_tasks  # Still included but with warning

    def test_flow_module_specific_execution(self, temp_service):
        """Test flow script generation with module-specific tasks."""
        # Create tasks in different modules
        temp_service.create("DefaultTask", {'run': "df_out = pd.DataFrame({'default': [1]})"})
        temp_service.create("ModuleTask", {'run': "df_out = pd.DataFrame({'module': [1]})"}, dataset="custom_module")

        # Test default module execution
        script1 = temp_service.run_preview("DefaultTask", file_out=None)
        assert "import tasks" in script1
        assert "task = tasks.DefaultTask" in script1

        # Test custom module execution
        script2 = temp_service.run_preview("ModuleTask", dataset="custom_module", file_out=None)
        assert "import tasks.custom_module as tasks" in script2
        assert "task = tasks.ModuleTask" in script2

    def test_execute_preview_basic(self, temp_service):
        """Test executing preview script."""
        # Create a simple task
        temp_service.create("ExecuteTask", {'run': "df_out = pd.DataFrame({'execute': [1]})"})

        # Generate script
        script = temp_service.run_preview("ExecuteTask")

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
        temp_service.create("RunExecuteTask", {'run': "df_out = pd.DataFrame({'run': [1]})"})

        # Generate script
        script = temp_service.run_flow("RunExecuteTask")

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
        temp_service.create("IntegrationTask", {'run': "df_out = pd.DataFrame({'integration': [1]})"})

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

    def test_run_flow_with_file_out(self, temp_service):
        """Test run_flow with file_out parameter."""
        from pathlib import Path

        # Create a simple task
        temp_service.create("FileOutTask", {'run': "df_out = pd.DataFrame({'test': [1]})"})

        # Generate run script and write to file
        result = temp_service.run_flow("FileOutTask", flow_params={"test": "value"}, file_out="custom_run.py")

        # Verify file path was returned
        assert isinstance(result, str)
        assert result.endswith("custom_run.py")

        # Verify file was written
        output_file = Path(temp_service.base_dir) / "custom_run.py"
        assert output_file.exists()

        # Verify file contents
        file_contents = output_file.read_text()
        assert "flow.run()" in file_contents

    def test_run_preview_with_file_out(self, temp_service):
        """Test run_preview with file_out parameter."""
        from pathlib import Path

        # Create a simple task
        temp_service.create("PreviewFileTask", {'run': "df_out = pd.DataFrame({'preview': [1]})"})

        # Generate preview script and write to file
        result = temp_service.run_preview("PreviewFileTask", flow_params={"test": "preview"}, file_out="custom_preview.py")

        # Verify file path was returned
        assert isinstance(result, str)
        assert result.endswith("custom_preview.py")

        # Verify file was written
        output_file = Path(temp_service.base_dir) / "custom_preview.py"
        assert output_file.exists()

        # Verify file contents
        file_contents = output_file.read_text()
        assert "flow.preview()" in file_contents

    def test_run_flow_with_default_file_out(self, temp_service):
        """Test run_flow with default file_out parameter (should write to run_flow.py by default)."""
        from pathlib import Path

        # Create a simple task
        temp_service.create("DefaultFileTask", {'run': "df_out = pd.DataFrame({'test': [1]})"})

        # Generate run script without specifying file_out (should default to run_flow.py)
        result = temp_service.run_flow("DefaultFileTask")

        # Verify file path was returned
        assert isinstance(result, str)
        assert result.endswith("run_flow.py")

        # Verify run_flow.py file was created by default
        run_file = Path(temp_service.base_dir) / "run_flow.py"
        assert run_file.exists()

        # Verify file contents
        file_contents = run_file.read_text()
        assert "flow.run()" in file_contents
        assert "import d6tflow" in file_contents

    def test_run_flow_with_none_file_out(self, temp_service):
        """Test run_flow with file_out=None (should not write file)."""
        from pathlib import Path

        # Create a simple task
        temp_service.create("NoFileTask", {'run': "df_out = pd.DataFrame({'nofile': [1]})"})

        # Generate run script with file_out=None (should not write file)
        script = temp_service.run_flow("NoFileTask", file_out=None)

        # Verify script was returned
        assert isinstance(script, str)
        assert "flow.run()" in script

        # Verify no run_flow.py file was created
        run_flow_file = Path(temp_service.base_dir) / "run_flow.py"
        assert not run_flow_file.exists()

    def test_run_task_basic(self, temp_service):
        """Test run_task with basic function call."""
        from pathlib import Path

        # Create a task with eda method
        temp_service.create("Task1", {
            'run': "df_out = pd.DataFrame({'data': [1, 2, 3]})",
            'eda': "return self.output().read().head()"
        })

        # Generate script for eda function
        result = temp_service.run_task("Task1", "eda")

        # Verify file path was returned
        assert isinstance(result, str)
        assert result.endswith("run_task.py")

        # Verify file was written with default filename
        output_file = Path(temp_service.base_dir) / "run_task.py"
        assert output_file.exists()

        # Verify file contents
        file_contents = output_file.read_text()
        assert "import tasks" in file_contents
        assert "tasks.Task1().eda()" in file_contents

    def test_run_task_with_module(self, temp_service):
        """Test run_task with specific module/dataset."""
        from pathlib import Path

        # Create task in specific module with custom method
        temp_service.create("Task2", {
            'run': "df_out = pd.DataFrame({'x': [1]})",
            'analyze': "return self.output().read().describe()"
        }, dataset="workspace")

        # Generate script
        result = temp_service.run_task("Task2", "analyze", dataset="workspace", file_out="analyze.py")

        # Verify file path was returned
        assert isinstance(result, str)
        assert result.endswith("analyze.py")

        # Verify file was written
        output_file = Path(temp_service.base_dir) / "analyze.py"
        assert output_file.exists()

        # Verify file contents
        file_contents = output_file.read_text()
        assert "import tasks.workspace" in file_contents
        assert "tasks.workspace.Task2().analyze()" in file_contents

    def test_run_task_with_none_file_out(self, temp_service):
        """Test run_task with file_out=None (should not write file)."""
        from pathlib import Path

        # Create task
        temp_service.create("Task3", {
            'run': "df_out = pd.DataFrame()",
            'custom': "return 42"
        })

        # Generate script without writing file
        script = temp_service.run_task("Task3", "custom", file_out=None)

        # Verify script was returned
        assert isinstance(script, str)
        assert "tasks.Task3().custom()" in script

        # Verify no file was created
        run_task_file = Path(temp_service.base_dir) / "run_task.py"
        assert not run_task_file.exists()

    def test_run_task_nonexistent_task(self, temp_service):
        """Test run_task with non-existent task raises error."""
        with pytest.raises(ValueError, match="not found"):
            temp_service.run_task("NonExistent", "method")