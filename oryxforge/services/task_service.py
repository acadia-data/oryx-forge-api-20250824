import ast
from pathlib import Path
import textwrap
import keyword
import re
import subprocess
import tempfile
from loguru import logger


class TaskService:
    def __init__(self, base_module: str = "tasks", base_dir: str = "."):
        self.base_module = base_module
        self.base_dir = Path(base_dir)
        self.base_module_dir = self.base_dir / base_module
        
        # Create base module directory and __init__.py
        self.base_module_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_init_file()
        
        # For backward compatibility, still support single-file mode
        self.single_file_mode = False
    
    def get_filename(self, module: str):
        """Get the filename for a specific module: base_dir/{base_module}/{module}.py or __init__.py if module is None"""
        if module is None:
            return self.base_module_dir / "__init__.py"
        return self.base_module_dir / f"{module}.py"
    
    def _ensure_init_file(self):
        """Create __init__.py if it doesn't exist."""
        init_file = self.base_module_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text("")

    def _parse_imports_string(self, imports_str: str) -> list[str]:
        """Parse import string into individual import statements. Keep it simple for now."""
        if not imports_str or not imports_str.strip():
            return []

        imports = []
        for line in imports_str.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            imports.append(line)

        return imports

    def _extract_imports_from_code(self, code: str) -> tuple[str, str]:
        """Extract import statements from code and return (cleaned_code, imports_string)."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            # If code can't be parsed, return as-is
            return code, ""

        imports = []
        non_import_nodes = []

        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imports.append(ast.unparse(node))
            else:
                non_import_nodes.append(node)

        # Reconstruct code without imports
        if non_import_nodes:
            cleaned_tree = ast.Module(body=non_import_nodes, type_ignores=[])
            cleaned_code = ast.unparse(cleaned_tree)
        else:
            cleaned_code = ""

        imports_string = "\n".join(imports) if imports else ""
        return cleaned_code, imports_string

    def _ensure_save_statement(self, code: str) -> str:
        """Ensure code ends with self.save(df_out) if not already present."""
        if not code.strip():
            return "df_out = None\nself.save(df_out)"

        # Check if code already has self.save() call
        if "self.save(" in code:
            return code

        # Add self.save(df_out) at the end
        return code.rstrip() + "\nself.save(df_out)"

    def _get_existing_imports(self, tree) -> dict[str, str | None]:
        """Get existing imports as {module: alias} dict."""
        existing = {}
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    existing[alias.name] = alias.asname
        return existing
    
    def _merge_imports(self, tree, new_imports_str: str):
        """Merge new imports with existing ones in the AST tree."""
        if not new_imports_str:
            return
            
        # Get existing imports as strings for simple comparison
        existing_import_strings = set()
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                existing_import_strings.add(ast.unparse(node))
        
        new_imports = self._parse_imports_string(new_imports_str)
        
        # Find the position after the last import statement
        last_import_index = 0
        for i, node in enumerate(tree.body):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                last_import_index = i + 1
        
        # Add new imports that don't already exist
        for import_str in new_imports:
            if import_str not in existing_import_strings:
                # Parse the import string and create AST node
                try:
                    import_ast = ast.parse(import_str).body[0]
                    # Insert after the last existing import
                    tree.body.insert(last_import_index, import_ast)
                    last_import_index += 1  # Update position for next import
                    logger.info(f"Added import: {import_str}")
                except SyntaxError:
                    logger.error(f"Invalid import syntax: {import_str}")
            else:
                logger.debug(f"Import already exists: {import_str}")

    def _ensure_imports(self, tree):
        """Ensure required imports are present in the given AST tree."""
        needed_imports_str = "import d6tflow\nimport pandas as pd"
        self._merge_imports(tree, needed_imports_str)

    def _find_class(self, tree, task: str):
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == task:
                return node
        return None

    def _sanitize_module_name(self, module: str) -> str:
        """Auto-sanitize to valid module name (snake_case)."""
        if module is None:
            return None
        if not module or not str(module).strip():
            return "default_module"
        
        module = str(module).strip()
        
        # Convert camelCase/PascalCase to snake_case
        module = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', module)
        # Replace spaces, hyphens, dots with underscores
        module = re.sub(r'[\s\-\.]+', '_', module)
        # Keep only alphanumeric and underscores
        module = re.sub(r'[^a-zA-Z0-9_]', '', module)
        # Convert to lowercase
        module = module.lower()
        # Remove consecutive underscores
        module = re.sub(r'_{2,}', '_', module)
        # Remove leading/trailing underscores
        module = module.strip('_')
        
        # Handle edge cases
        if not module or module.isdigit():
            module = "module_" + module if module else "default_module"
        elif module[0].isdigit():
            module = "m_" + module
        
        # Handle Python keywords
        if keyword.iskeyword(module):
            module += "_mod"
        
        # Length limit
        if len(module) > 50:
            module = module[:47] + "_mod"
        
        return module

    def _sanitize_task_name(self, task: str) -> str:
        """Auto-sanitize to valid class name (PascalCase)."""
        if not task or not str(task).strip():
            return "DefaultTask"
        
        task = str(task).strip()
        
        # If it's already a valid Python identifier and starts with uppercase, keep it
        if task.isidentifier() and task[0].isupper():
            # Handle Python keywords
            if keyword.iskeyword(task.lower()):
                task += "Task"
            # Length limit
            if len(task) > 50:
                task = task[:46] + "Task"
            return task
        
        # Split on common separators and camelCase boundaries
        # Handle camelCase/PascalCase by inserting spaces before uppercase letters
        spaced = re.sub(r'([a-z])([A-Z])', r'\1 \2', task)
        # Split on spaces, hyphens, underscores, etc.
        words = re.split(r'[^a-zA-Z0-9]+', spaced)
        # Filter out empty strings and pure numbers
        words = [w for w in words if w and not w.isdigit()]
        
        if not words:
            return "DefaultTask"
        
        # Convert to PascalCase
        sanitized = ''.join(word.capitalize() for word in words)
        
        # Ensure starts with letter
        if sanitized[0].isdigit():
            sanitized = "Task" + sanitized
        
        # Handle Python keywords
        if keyword.iskeyword(sanitized.lower()):
            sanitized += "Task"
        
        # Length limit
        if len(sanitized) > 50:
            sanitized = sanitized[:46] + "Task"
        
        return sanitized

    def _sanitize_inputs(self, inputs: list[str]) -> list[str]:
        """Auto-clean input task names."""
        if not inputs:
            return []
        
        clean_inputs = []
        changes = []
        
        for inp in inputs:
            clean_inp = self._sanitize_task_name(inp)
            clean_inputs.append(clean_inp)
            if inp != clean_inp:
                changes.append(f"'{inp}' -> '{clean_inp}'")
        
        if changes:
            logger.info(f"Auto-cleaned inputs: {', '.join(changes)}")
        
        return clean_inputs

    def _auto_clean_names(self, module: str, task: str) -> tuple[str, str]:
        """Auto-clean both module and task names, log changes."""
        original_module, original_task = module, task
        
        clean_module = self._sanitize_module_name(module)
        clean_task = self._sanitize_task_name(task)
        
        # Log changes if any
        changes = []
        if original_module != clean_module:
            if clean_module is None:
                changes.append(f"module: '{original_module}' -> 'tasks/__init__.py'")
            else:
                changes.append(f"module: '{original_module}' -> '{clean_module}'")
        if original_task != clean_task:
            changes.append(f"task: '{original_task}' -> '{clean_task}'")
        
        if changes:
            logger.info(f"Auto-cleaned: {', '.join(changes)}")
        
        return clean_module, clean_task

    def _sanitize_method_name(self, method_name: str) -> str:
        """Sanitize method name to be valid Python identifier."""
        if not method_name or not str(method_name).strip():
            return "default_method"

        method_name = str(method_name).strip()

        # Convert to snake_case and clean up
        method_name = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', method_name)
        method_name = re.sub(r'[\s\-\.]+', '_', method_name)
        method_name = re.sub(r'[^a-zA-Z0-9_]', '', method_name)
        method_name = method_name.lower()
        method_name = re.sub(r'_{2,}', '_', method_name)
        method_name = method_name.strip('_')

        # Handle edge cases
        if not method_name or method_name.isdigit():
            method_name = "method_" + method_name if method_name else "default_method"
        elif method_name[0].isdigit():
            method_name = "m_" + method_name

        # Handle Python keywords and built-in method names
        if keyword.iskeyword(method_name) or method_name in ['run', 'input', 'output', 'save']:
            method_name += "_method"

        # Length limit
        if len(method_name) > 50:
            method_name = method_name[:42] + "_method"

        return method_name

    def _generate_additional_methods(self, code_methods: dict[str, str]) -> str:
        """Generate additional class methods from code_methods dict."""
        if not code_methods:
            return ""

        methods = []
        for method_name, method_code in code_methods.items():
            # Sanitize method name to be valid Python identifier
            clean_method_name = self._sanitize_method_name(method_name)

            method_source = f"""    def {clean_method_name}(self):
{textwrap.indent(method_code, '        ')}"""
            methods.append(method_source)

        return "\n\n" + "\n\n".join(methods)

    def _generate_class_source(self, task: str, code: str, inputs: list[str], code_methods: dict[str, str] = None) -> str:
        """Generate source code for a task class."""
        decorator_str = ""
        if inputs:
            inputs_str = ", ".join(inputs)
            decorator_str = f"@d6tflow.requires({inputs_str})\n"

        # Ensure code has self.save(df_out) at the end
        code = self._ensure_save_statement(code)

        # Generate additional methods
        additional_methods = self._generate_additional_methods(code_methods or {})

        class_source = f"""{decorator_str}class {task}(d6tflow.tasks.TaskPqPandas):
    def run(self):
{textwrap.indent(code, '        ')}{additional_methods}"""
        return class_source

    # ---------- Internal Helpers ----------
    
    def _prepare_task_operation(self, module: str, task: str):
        """Common preparation for task operations: clean names and get filename."""
        module, task = self._auto_clean_names(module, task)
        filename = self.get_filename(module)
        return module, task, filename
    
    def _get_module_display(self, module: str) -> str:
        """Get display name for module (tasks/__init__.py if None)."""
        return "tasks/__init__.py" if module is None else module
    
    def _get_file_display(self, module: str) -> str:
        """Get display name for file (tasks/__init__.py if None, else {module}.py)."""
        return "tasks/__init__.py" if module is None else f"{module}.py"

    # ---------- CRUD Methods ----------

    def create(self, task: str, code: str, module: str = None, inputs: list[str] = None, imports: str = None, code_methods: dict[str, str] = None):
        """Create a new task class (fails if already exists)."""
        module, task, filename = self._prepare_task_operation(module, task)
        inputs = self._sanitize_inputs(inputs or [])

        # Load existing file or create new tree
        if filename.exists():
            tree = ast.parse(filename.read_text())
        else:
            tree = ast.parse("")

        # Ensure base imports first
        self._ensure_imports(tree)

        # Add custom imports if provided
        if imports:
            self._merge_imports(tree, imports)

        if self._find_class(tree, task):
            raise ValueError(f"Class {task} already exists in {module}")

        class_source = self._generate_class_source(task, code, inputs, code_methods)
        class_ast = ast.parse(class_source)
        class_def = class_ast.body[0]

        tree.body.append(class_def)
        self._save_file(filename, tree)
        status_msg = f"Created {task} in {self._get_module_display(module)}"
        logger.success(status_msg)
        return status_msg

    def upsert(self, task: str, code: str, module: str = None, inputs: list[str] = None, imports: str = None, code_methods: dict[str, str] = None):
        """Create a new task class or update if it already exists (upsert)."""
        module, task, filename = self._prepare_task_operation(module, task)

        # Check if task already exists
        if filename.exists():
            tree = ast.parse(filename.read_text())
            existing_class = self._find_class(tree, task)
            if existing_class:
                # Update existing class
                return self.update(task, module=module, new_code=code, new_inputs=inputs, new_imports=imports, new_code_methods=code_methods)

        # Create new class
        return self.create(task, code, module=module, inputs=inputs, imports=imports, code_methods=code_methods)

    def read(self, task: str, module: str = None, method_only: bool = True) -> str:
        """Return the source code for a given class or just run() method body."""
        module, task, filename = self._prepare_task_operation(module, task)
        
        if not filename.exists():
            raise ValueError(f"File {self._get_file_display(module)} not found")
        
        tree = ast.parse(filename.read_text())
        cls = self._find_class(tree, task)
        if not cls:
            raise ValueError(f"Class {task} not found in {self._get_module_display(module)}")
        
        if method_only:
            # Find and return just run() method body
            for node in cls.body:
                if isinstance(node, ast.FunctionDef) and node.name == "run":
                    # Return the method body as properly formatted code
                    body_code = []
                    for stmt in node.body:
                        body_code.append(ast.unparse(stmt))
                    return '\n'.join(body_code)
            raise ValueError(f"run() method not found in {task}")
        
        return ast.unparse(cls)

    def update(
        self,
        task: str,
        module: str = None,
        new_code: str = None,
        new_inputs: list[str] = None,
        new_imports: str = None,
        new_code_methods: dict[str, str] = None,
    ):
        """
        Update an existing class.
        - new_code: replace run() method body
        - new_inputs: replace @d6tflow.requires(...)
        - new_imports: add new imports to the file
        - new_code_methods: replace all custom methods with new ones from dict
        """
        module, task, filename = self._prepare_task_operation(module, task)
        if new_inputs is not None:
            new_inputs = self._sanitize_inputs(new_inputs)


        if not filename.exists():
            raise ValueError(f"File {self._get_file_display(module)} not found")

        tree = ast.parse(filename.read_text())
        cls = self._find_class(tree, task)
        if not cls:
            raise ValueError(f"Class {task} not found in {self._get_module_display(module)}")

        # Add new imports if provided
        if new_imports:
            self._merge_imports(tree, new_imports)

        if new_code:
            # Ensure code has self.save(df_out) at the end
            new_code = self._ensure_save_statement(new_code)

            for node in cls.body:
                if isinstance(node, ast.FunctionDef) and node.name == "run":
                    node.body = ast.parse(textwrap.dedent(new_code)).body
                    break
            else:
                raise ValueError(f"run() not found in {task}")

        if new_inputs is not None:
            # Remove existing @d6tflow.requires decorators
            cls.decorator_list = [
                d
                for d in cls.decorator_list
                if not (
                    isinstance(d, ast.Call)
                    and isinstance(d.func, ast.Attribute)
                    and d.func.attr == "requires"
                )
            ]
            # Add new decorator if inputs exist
            if new_inputs:
                inputs_str = ", ".join(new_inputs)
                # Create decorator AST manually since we need just the decorator
                decorator_ast = ast.Call(
                    func=ast.Attribute(
                        value=ast.Name("d6tflow", ast.Load()),
                        attr="requires",
                        ctx=ast.Load()
                    ),
                    args=[ast.Name(inp, ast.Load()) for inp in new_inputs],
                    keywords=[]
                )
                cls.decorator_list.insert(0, decorator_ast)

        if new_code_methods:
            # Remove existing custom methods (keep only run, input, output, save)
            standard_methods = {'run', 'input', 'output', 'save'}
            cls.body = [
                node for node in cls.body
                if not (isinstance(node, ast.FunctionDef) and node.name not in standard_methods)
            ]

            # Add new methods
            for method_name, method_code in new_code_methods.items():
                clean_method_name = self._sanitize_method_name(method_name)

                # Create method AST
                method_ast = ast.parse(f"""def {clean_method_name}(self):
{textwrap.indent(method_code, '    ')}""").body[0]

                cls.body.append(method_ast)

        self._save_file(filename, tree)
        status_msg = f"Updated {task} in {self._get_module_display(module)}"
        logger.success(status_msg)
        return status_msg

    def delete(self, task: str, module: str = None):
        """Delete a class definition by task name."""
        module, task, filename = self._prepare_task_operation(module, task)
        
        if not filename.exists():
            raise ValueError(f"File {self._get_file_display(module)} not found")
        
        tree = ast.parse(filename.read_text())
        new_body = [
            n
            for n in tree.body
            if not (isinstance(n, ast.ClassDef) and n.name == task)
        ]
        if len(new_body) == len(tree.body):
            raise ValueError(f"Class {task} not found in {self._get_module_display(module)}")
        tree.body = new_body
        self._save_file(filename, tree)
        logger.success(f"Deleted {task} from {self._get_module_display(module)}")

    def list_tasks(self, module: str = None):
        """List all defined task class names in a specific module file."""
        original_module = module
        module = self._sanitize_module_name(module)
        if original_module != module:
            if module is None:
                logger.info(f"Auto-cleaned module: '{original_module}' -> 'tasks/__init__.py'")
            else:
                logger.info(f"Auto-cleaned module: '{original_module}' -> '{module}'")
        filename = self.get_filename(module)
        
        if not filename.exists():
            return []
        
        tree = ast.parse(filename.read_text())
        return [n.name for n in tree.body if isinstance(n, ast.ClassDef)]

    def list_modules(self):
        """List all available modules by scanning the base module directory."""
        if not self.base_module_dir.exists():
            return []
        
        modules = []
        for file_path in self.base_module_dir.iterdir():
            if file_path.is_file() and file_path.name.endswith(".py") and file_path.name != "__init__.py":
                # Extract module name from filename pattern: {module}.py
                module_name = file_path.name[:-3]  # Remove .py extension
                modules.append(module_name)
        
        return sorted(modules)

    def list_tasks_by_module(self, module: str = None):
        """List all task classes in a given module using AST parsing."""
        original_module = module
        module = self._sanitize_module_name(module)
        if original_module != module:
            if module is None:
                logger.info(f"Auto-cleaned module: '{original_module}' -> 'tasks/__init__.py'")
            else:
                logger.info(f"Auto-cleaned module: '{original_module}' -> '{module}'")
        filename = self.get_filename(module)
        
        if not filename.exists():
            return []
        
        tree = ast.parse(filename.read_text())
        return [n.name for n in tree.body if isinstance(n, ast.ClassDef)]

    def rename_task(self, old_task: str, new_task: str, module: str = None):
        """Rename a task class and update dependency references."""
        original_module, original_old_task, original_new_task = module, old_task, new_task
        
        module = self._sanitize_module_name(module)
        old_task = self._sanitize_task_name(old_task)
        new_task = self._sanitize_task_name(new_task)
        
        filename = self.get_filename(module)
        
        # Log changes
        changes = []
        if original_module != module:
            if module is None:
                changes.append(f"module: '{original_module}' -> 'tasks/__init__.py'")
            else:
                changes.append(f"module: '{original_module}' -> '{module}'")
        if original_old_task != old_task:
            changes.append(f"old task: '{original_old_task}' -> '{old_task}'")
        if original_new_task != new_task:
            changes.append(f"new task: '{original_new_task}' -> '{new_task}'")
        
        if changes:
            logger.info(f"Auto-cleaned: {', '.join(changes)}")
        
        if not filename.exists():
            raise ValueError(f"File {self._get_file_display(module)} not found")
        
        tree = ast.parse(filename.read_text())
        cls = self._find_class(tree, old_task)
        if not cls:
            raise ValueError(f"Class {old_task} not found in {self._get_module_display(module)}")
        if self._find_class(tree, new_task):
            raise ValueError(f"Class {new_task} already exists in {self._get_module_display(module)}")

        # Rename class
        cls.name = new_task

        # Update all @d6tflow.requires(old_task) to new_task
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                for dec in node.decorator_list:
                    if (
                        isinstance(dec, ast.Call)
                        and isinstance(dec.func, ast.Attribute)
                        and dec.func.attr == "requires"
                    ):
                        for i, arg in enumerate(dec.args):
                            if isinstance(arg, ast.Name) and arg.id == old_task:
                                dec.args[i] = ast.Name(new_task, ast.Load())

        self._save_file(filename, tree)
        logger.success(f"Renamed {old_task} -> {new_task} in {self._get_module_display(module)} and updated dependencies")

    # ---------- Flow Execution ----------

    def preview_flow(self, task: str, module: str = None, 
                    flow_params: dict = None, reset_tasks: list[str] = None) -> str:
        """Generate and execute a preview script for a d6tflow workflow."""
        script = self.create_preview(task, module, flow_params, reset_tasks)
        return self.execute_preview(script)

    def create_run(self, task: str, module: str = None,
                  flow_params: dict = None, reset_tasks: list[str] = None) -> str:
        """Generate a run script for a d6tflow workflow."""
        return self._generate_flow_script(task, module, flow_params, reset_tasks, preview_only=False)

    def create_preview(self, task: str, module: str = None, 
                      flow_params: dict = None, reset_tasks: list[str] = None) -> str:
        """Generate a preview script for a d6tflow workflow."""
        return self._generate_flow_script(task, module, flow_params, reset_tasks, preview_only=True)

    def execute_run(self, script: str) -> str:
        """Execute a run script using subprocess."""
        return self._execute_script(script)

    def execute_preview(self, script: str) -> str:
        """Execute a preview script using subprocess."""
        return self._execute_script(script)

    def _validate_flow_task(self, task: str, module: str) -> tuple[str, str]:
        """Internal method to validate flow task exists."""
        # Reuse existing validation
        module, task, _ = self._prepare_task_operation(module, task)
        
        # Validate that the target task exists
        if module is None:
            available_tasks = self.list_tasks()
        else:
            available_tasks = self.list_tasks(module)
        
        if task not in available_tasks:
            raise ValueError(f"Task {task} not found in {self._get_module_display(module)}")
        
        return module, task

    def _validate_reset_tasks(self, reset_tasks: list[str], target_module: str) -> list[str]:
        """Validate that reset tasks exist and return sanitized names."""
        if not reset_tasks:
            return []
        
        validated_tasks = []
        for reset_task in reset_tasks:
            # Sanitize task name
            clean_task = self._sanitize_task_name(reset_task)
            
            # Check if task exists in the target module
            if target_module is None:
                # Check in default module (tasks/__init__.py)
                available_tasks = self.list_tasks()
            else:
                # Check in specific module
                available_tasks = self.list_tasks(target_module)
            
            if clean_task not in available_tasks:
                logger.warning(f"Reset task '{reset_task}' (cleaned: '{clean_task}') not found in {self._get_module_display(target_module)}")
                # Continue anyway - d6tflow will handle the error
            
            validated_tasks.append(clean_task)
        
        return validated_tasks

    def _generate_flow_script(self, task: str, module: str, flow_params: dict, reset_tasks: list[str], preview_only: bool = False) -> str:
        """Generate the flow_run.py script content using string manipulation."""
        # Validate task exists
        module, task = self._validate_flow_task(task, module)
        
        # Validate reset_tasks exist
        reset_tasks = self._validate_reset_tasks(reset_tasks or [], module)
        
        # Import section
        if module is None:
            import_line = "import tasks"
            task_ref = f"tasks.{task}"
        else:
            import_line = f"import tasks.{module} as tasks"  
            task_ref = f"tasks.{task}"
        
        # Parameters section
        params_str = repr(flow_params or {})
        
        # Reset section
        reset_lines = []
        for reset_task in (reset_tasks or []):
            reset_lines.append(f"flow.reset(tasks.{reset_task})")
        reset_section = "\n".join(reset_lines)
        
        # Action section
        action = "flow.preview()" if preview_only else "flow.run()"

        # Generate complete script with path fix
        script = f"""import sys
import os
sys.path.insert(0, os.getcwd())

import d6tflow
{import_line}

# Parameters
params = {params_str}

# Target task
task = {task_ref}

# Create workflow
flow = d6tflow.Workflow(task=task, params=params)

# Reset tasks
{reset_section}

# Execute
{action}
"""
        
        logger.debug(f"Generated flow script:\n{script}")
        return script

    def _execute_script(self, script: str) -> str:
        """Execute the generated Python script and return output."""
        try:
            # Create temporary script file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(script)
                script_path = f.name
            
            # Execute script using subprocess
            result = subprocess.run(
                ['python', script_path],
                cwd=str(self.base_dir),
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            # Clean up temporary file
            Path(script_path).unlink()
            
            # Process results
            if result.returncode == 0:
                output = result.stdout.strip()
                if result.stderr.strip():
                    output += f"\n\nWarnings/Info:\n{result.stderr.strip()}"
                logger.success("Flow execution completed successfully")
                return output
            else:
                error_msg = f"Flow execution failed with return code {result.returncode}\n"
                if result.stdout.strip():
                    error_msg += f"stdout: {result.stdout.strip()}\n"
                if result.stderr.strip():
                    error_msg += f"stderr: {result.stderr.strip()}"
                logger.error(error_msg)
                return error_msg
                
        except subprocess.TimeoutExpired:
            error_msg = "Flow execution timed out after 5 minutes"
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"Error executing flow script: {str(e)}"
            logger.error(error_msg)
            return error_msg

    # ---------- Internal ----------

    def _save_file(self, filename: Path, tree):
        """Save the AST tree to a file."""
        formatted_code = ast.unparse(tree)
        filename.write_text(formatted_code)
