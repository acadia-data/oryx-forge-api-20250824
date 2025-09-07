import ast
from pathlib import Path
import textwrap


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
        """Get the filename for a specific module: base_dir/{base_module}/{module}.py"""
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

    def _find_class(self, tree, name: str):
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == name:
                return node
        return None

    def _generate_class_source(self, name: str, code: str, dependencies: list[str]) -> str:
        """Generate source code for a task class."""
        decorator_str = ""
        if dependencies:
            deps_str = ", ".join(dependencies)
            decorator_str = f"@d6tflow.requires({deps_str})\n"
        
        class_source = f"""{decorator_str}class {name}(d6tflow.tasks.PandasPq):
    def run(self):
{textwrap.indent(code, '        ')}"""
        return class_source

    # ---------- CRUD Methods ----------

    def create(self, module: str, task: str, code: str, dependencies: list[str]):
        """Create a new task class (fails if already exists)."""
        filename = self.get_filename(module)
        
        # Load existing file or create new tree
        if filename.exists():
            tree = ast.parse(filename.read_text())
        else:
            tree = ast.parse("")
            self._ensure_imports(tree)
        
        if self._find_class(tree, task):
            raise ValueError(f"Class {task} already exists in {module}")

        class_source = self._generate_class_source(task, code, dependencies)
        class_ast = ast.parse(class_source)
        class_def = class_ast.body[0]
        
        tree.body.append(class_def)
        self._save_file(filename, tree)
        print(f"✅ Created {task} in {module}")

    def upsert(self, module: str, task: str, code: str, dependencies: list[str]):
        """Create a new task class or update if it already exists (upsert)."""
        filename = self.get_filename(module)
        
        # Load existing file or create new tree
        if filename.exists():
            tree = ast.parse(filename.read_text())
        else:
            tree = ast.parse("")
            self._ensure_imports(tree)
        
        existing_class = self._find_class(tree, task)
        if existing_class:
            # Update existing class
            self.update(module, task, new_code=code, new_dependencies=dependencies)
        else:
            # Create new class
            class_source = self._generate_class_source(task, code, dependencies)
            class_ast = ast.parse(class_source)
            class_def = class_ast.body[0]
            
            tree.body.append(class_def)
            self._save_file(filename, tree)
            print(f"✅ Created {task} in {module}")

    def read(self, module: str, task: str) -> str:
        """Return the source code for a given class."""
        filename = self.get_filename(module)
        
        if not filename.exists():
            raise ValueError(f"File {module}.py not found")
        
        tree = ast.parse(filename.read_text())
        cls = self._find_class(tree, task)
        if not cls:
            raise ValueError(f"Class {task} not found in {module}")
        return ast.unparse(cls)

    def update(
        self,
        module: str,
        task: str,
        new_code: str = None,
        new_dependencies: list[str] = None,
    ):
        """
        Update an existing class.
        - new_code: replace run() method body
        - new_dependencies: replace @d6tflow.requires(...)
        """
        filename = self.get_filename(module)
        
        if not filename.exists():
            raise ValueError(f"File {module}.py not found")
        
        tree = ast.parse(filename.read_text())
        cls = self._find_class(tree, task)
        if not cls:
            raise ValueError(f"Class {task} not found in {module}")

        if new_code:
            for node in cls.body:
                if isinstance(node, ast.FunctionDef) and node.name == "run":
                    node.body = ast.parse(textwrap.dedent(new_code)).body
                    break
            else:
                raise ValueError(f"run() not found in {task}")

        if new_dependencies is not None:
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
            # Add new decorator if dependencies exist
            if new_dependencies:
                deps_str = ", ".join(new_dependencies)
                # Create decorator AST manually since we need just the decorator
                decorator_ast = ast.Call(
                    func=ast.Attribute(
                        value=ast.Name("d6tflow", ast.Load()),
                        attr="requires",
                        ctx=ast.Load()
                    ),
                    args=[ast.Name(dep, ast.Load()) for dep in new_dependencies],
                    keywords=[]
                )
                cls.decorator_list.insert(0, decorator_ast)

        self._save_file(filename, tree)
        print(f"✅ Updated {task} in {module}")

    def delete(self, module: str, task: str):
        """Delete a class definition by name."""
        filename = self.get_filename(module)
        
        if not filename.exists():
            raise ValueError(f"File {module}.py not found")
        
        tree = ast.parse(filename.read_text())
        new_body = [
            n
            for n in tree.body
            if not (isinstance(n, ast.ClassDef) and n.name == task)
        ]
        if len(new_body) == len(tree.body):
            raise ValueError(f"Class {task} not found in {module}")
        tree.body = new_body
        self._save_file(filename, tree)
        print(f"✅ Deleted {task} from {module}")

    def list_tasks(self, module: str):
        """List all defined task class names in a specific module file."""
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

    def list_tasks_by_module(self, module: str):
        """List all task classes in a given module using AST parsing."""
        filename = self.get_filename(module)
        
        if not filename.exists():
            return []
        
        tree = ast.parse(filename.read_text())
        return [n.name for n in tree.body if isinstance(n, ast.ClassDef)]

    def rename(self, module: str, old_task: str, new_task: str):
        """Rename a task class and update dependency references."""
        filename = self.get_filename(module)
        
        if not filename.exists():
            raise ValueError(f"File {module}.py not found")
        
        tree = ast.parse(filename.read_text())
        cls = self._find_class(tree, old_task)
        if not cls:
            raise ValueError(f"Class {old_task} not found in {module}")
        if self._find_class(tree, new_task):
            raise ValueError(f"Class {new_task} already exists in {module}")

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
        print(f"✅ Renamed {old_task} → {new_task} in {module} and updated dependencies")

    # ---------- Internal ----------

    def _save_file(self, filename: Path, tree):
        """Save the AST tree to a file."""
        formatted_code = ast.unparse(tree)
        filename.write_text(formatted_code)
