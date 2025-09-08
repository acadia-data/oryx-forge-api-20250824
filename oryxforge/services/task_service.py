import ast
from pathlib import Path
import textwrap
import keyword
import re
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

    def _ensure_imports(self, tree):
        """Ensure required imports are present in the given AST tree."""
        needed_imports = [
            ("d6tflow", None),
            ("pandas", "pd"),
        ]
        existing_imports = {
            n.names[0].name if isinstance(n, ast.Import) else n.module
            for n in tree.body
            if isinstance(n, (ast.Import, ast.ImportFrom))
        }
        for mod, alias in needed_imports:
            if mod not in existing_imports:
                if alias:
                    tree.body.insert(
                        0, ast.Import(names=[ast.alias(name=mod, asname=alias)])
                    )
                else:
                    tree.body.insert(0, ast.Import(names=[ast.alias(name=mod, asname=None)]))

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

    def _generate_class_source(self, task: str, code: str, inputs: list[str]) -> str:
        """Generate source code for a task class."""
        decorator_str = ""
        if inputs:
            inputs_str = ", ".join(inputs)
            decorator_str = f"@d6tflow.requires({inputs_str})\n"
        
        class_source = f"""{decorator_str}class {task}(d6tflow.tasks.PandasPq):
    def run(self):
{textwrap.indent(code, '        ')}"""
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

    def create(self, task: str, code: str, module: str = None, inputs: list[str] = None):
        """Create a new task class (fails if already exists)."""
        module, task, filename = self._prepare_task_operation(module, task)
        inputs = self._sanitize_inputs(inputs or [])
        
        # Load existing file or create new tree
        if filename.exists():
            tree = ast.parse(filename.read_text())
        else:
            tree = ast.parse("")
            self._ensure_imports(tree)
        
        if self._find_class(tree, task):
            raise ValueError(f"Class {task} already exists in {module}")

        class_source = self._generate_class_source(task, code, inputs)
        class_ast = ast.parse(class_source)
        class_def = class_ast.body[0]
        
        tree.body.append(class_def)
        self._save_file(filename, tree)
        logger.success(f"Created {task} in {self._get_module_display(module)}")

    def upsert(self, task: str, code: str, module: str = None, inputs: list[str] = None):
        """Create a new task class or update if it already exists (upsert)."""
        module, task, filename = self._prepare_task_operation(module, task)
        inputs = self._sanitize_inputs(inputs or [])
        
        # Load existing file or create new tree
        if filename.exists():
            tree = ast.parse(filename.read_text())
        else:
            tree = ast.parse("")
            self._ensure_imports(tree)
        
        existing_class = self._find_class(tree, task)
        if existing_class:
            # Update existing class
            self.update(task, module=module, new_code=code, new_inputs=inputs)
        else:
            # Create new class
            class_source = self._generate_class_source(task, code, inputs)
            class_ast = ast.parse(class_source)
            class_def = class_ast.body[0]
            
            tree.body.append(class_def)
            self._save_file(filename, tree)
            logger.success(f"Created {task} in {self._get_module_display(module)}")

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
    ):
        """
        Update an existing class.
        - new_code: replace run() method body
        - new_inputs: replace @d6tflow.requires(...)
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

        if new_code:
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

        self._save_file(filename, tree)
        logger.success(f"Updated {task} in {self._get_module_display(module)}")

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

    # ---------- Internal ----------

    def _save_file(self, filename: Path, tree):
        """Save the AST tree to a file."""
        formatted_code = ast.unparse(tree)
        filename.write_text(formatted_code)
