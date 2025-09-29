import ast
from pathlib import Path
import textwrap
import keyword
import re
import subprocess
import tempfile
from loguru import logger
from pydantic import BaseModel, ValidationError, field_validator
from typing import Optional


class InputSchema(BaseModel):
    """Schema for input dependencies."""
    dataset: Optional[str] = None
    sheet: str

    @field_validator('sheet')
    @classmethod
    def sheet_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('sheet cannot be empty')
        return v


class WorkflowService:
    def __init__(self, base_module: str = "tasks", base_dir: str = "."):
        self.base_module = base_module
        self.base_dir = Path(base_dir)
        self.base_module_dir = self.base_dir / base_module
        
        # Create base module directory and __init__.py
        self.base_module_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_init_file()
        
        # For backward compatibility, still support single-file mode
        self.single_file_mode = False
    
    def get_filename(self, dataset: str):
        """Get the filename for a specific dataset: base_dir/{base_module}/{dataset}.py or __init__.py if dataset is None"""
        if dataset is None:
            return self.base_module_dir / "__init__.py"
        return self.base_module_dir / f"{dataset}.py"
    
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
        """Get existing imports as {dataset: alias} dict."""
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
        needed_imports_str = """
import d6tflow
import pandas as pd
pd.set_option('display.max_columns', None)
"""
        self._merge_imports(tree, needed_imports_str)

    def _find_class(self, tree, sheet: str):
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == sheet:
                return node
        return None

    def _sanitize_dataset_name(self, dataset: str) -> str:
        """Auto-sanitize to valid dataset name (snake_case)."""
        if dataset is None:
            return None
        if not dataset or not str(dataset).strip():
            return "default_dataset"

        dataset = str(dataset).strip()
        
        # Convert camelCase/PascalCase to snake_case
        dataset = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', dataset)
        # Replace spaces, hyphens, dots with underscores
        dataset = re.sub(r'[\s\-\.]+', '_', dataset)
        # Keep only alphanumeric and underscores
        dataset = re.sub(r'[^a-zA-Z0-9_]', '', dataset)
        # Convert to lowercase
        dataset = dataset.lower()
        # Remove consecutive underscores
        dataset = re.sub(r'_{2,}', '_', dataset)
        # Remove leading/trailing underscores
        dataset = dataset.strip('_')

        # Handle edge cases
        if not dataset or dataset.isdigit():
            dataset = "dataset_" + dataset if dataset else "default_dataset"
        elif dataset[0].isdigit():
            dataset = "d_" + dataset

        # Handle Python keywords
        if keyword.iskeyword(dataset):
            dataset += "_ds"

        # Length limit
        if len(dataset) > 50:
            dataset = dataset[:47] + "_ds"

        return dataset

    def _sanitize_sheet_name(self, sheet: str) -> str:
        """Auto-sanitize to valid class name (PascalCase)."""
        if not sheet or not str(sheet).strip():
            return "DefaultSheet"

        sheet = str(sheet).strip()
        
        # If it's already a valid Python identifier and starts with uppercase, keep it
        if sheet.isidentifier() and sheet[0].isupper():
            # Handle Python keywords
            if keyword.iskeyword(sheet.lower()):
                sheet += "Sheet"
            # Length limit
            if len(sheet) > 50:
                sheet = sheet[:45] + "Sheet"
            return sheet

        # Split on common separators and camelCase boundaries
        # Handle camelCase/PascalCase by inserting spaces before uppercase letters
        spaced = re.sub(r'([a-z])([A-Z])', r'\1 \2', sheet)
        # Split on spaces, hyphens, underscores, etc.
        words = re.split(r'[^a-zA-Z0-9]+', spaced)
        # Filter out empty strings and pure numbers
        words = [w for w in words if w and not w.isdigit()]

        if not words:
            return "DefaultSheet"

        # Convert to PascalCase
        sanitized = ''.join(word.capitalize() for word in words)

        # Ensure starts with letter
        if sanitized[0].isdigit():
            sanitized = "Sheet" + sanitized

        # Handle Python keywords
        if keyword.iskeyword(sanitized.lower()):
            sanitized += "Sheet"

        # Length limit
        if len(sanitized) > 50:
            sanitized = sanitized[:45] + "Sheet"

        return sanitized

    def _sanitize_inputs(self, inputs: list[str]) -> list[str]:
        """Auto-clean input sheet names."""
        if not inputs:
            return []

        clean_inputs = []
        changes = []

        for inp in inputs:
            clean_inp = self._sanitize_sheet_name(inp)
            clean_inputs.append(clean_inp)
            if inp != clean_inp:
                changes.append(f"'{inp}' -> '{clean_inp}'")

        if changes:
            logger.info(f"Auto-cleaned inputs: {', '.join(changes)}")

        return clean_inputs

    def _process_inputs(self, inputs: list[dict] | list[str] | None, current_dataset: str = None) -> tuple[list[str], list[str], dict[str, str]]:
        """Process and validate inputs, return (class_names, datasets_to_import, metadata).

        Args:
            inputs: List of input specifications. Can be:
                    - List of dicts: [{'dataset': 'sources', 'sheet': 'Hpi'}, ...]
                    - List of strings: ['Hpi', 'Another'] (legacy format, assumes same dataset)
                    - None
            current_dataset: The dataset we're generating code for (to avoid self-imports)

        Returns:
            Tuple of (class_names, datasets_to_import, metadata) where:
            - class_names: List of class references for decorator (e.g., ['sources.Hpi', 'Tasks2'])
            - datasets_to_import: List of dataset names to import (excluding current_dataset)
            - metadata: Dict mapping string key to actual class reference (e.g., {'sources.Hpi': 'sources.Hpi'})
        """
        if not inputs:
            return [], [], {}

        # Handle legacy format (list of strings) - convert to dict format
        if inputs and isinstance(inputs[0], str):
            logger.info("Legacy inputs format detected (list of strings). Converting to dict format.")
            # Convert to dict format: ['Task1', 'Task2'] -> [{'dataset': current_dataset, 'sheet': 'Task1'}, ...]
            inputs = [{'dataset': current_dataset, 'sheet': sheet} for sheet in inputs]

        # Validate using pydantic
        validated_inputs = []
        try:
            for inp in inputs:
                validated = InputSchema(**inp)
                validated_inputs.append(validated)
        except ValidationError as e:
            raise ValueError(f"Invalid inputs schema: {e}")

        # Validate that datasets and sheets exist
        available_datasets = self.list_datasets()

        class_names = []
        datasets_to_import = set()
        metadata = {}

        for inp in validated_inputs:
            input_dataset = self._sanitize_dataset_name(inp.dataset) if inp.dataset else None
            input_sheet = self._sanitize_sheet_name(inp.sheet)

            # Validate dataset exists
            if input_dataset and input_dataset not in available_datasets:
                raise ValueError(f"Input dataset '{input_dataset}' does not exist. Available datasets: {available_datasets}")

            # Validate sheet exists in dataset
            sheets_in_dataset = self.list_sheets_by_dataset(input_dataset)
            if input_sheet not in sheets_in_dataset:
                dataset_display = input_dataset if input_dataset else "tasks/__init__.py"
                raise ValueError(f"Input sheet '{input_sheet}' does not exist in {dataset_display}. Available sheets: {sheets_in_dataset}")

            # Build class reference
            # Always use the full qualified name in the metadata key
            dataset_for_key = input_dataset if input_dataset else current_dataset
            if dataset_for_key:
                metadata_key = f"{dataset_for_key}.{input_sheet}"
            else:
                metadata_key = input_sheet

            if input_dataset and input_dataset != current_dataset:
                # Different dataset - need qualified name and import
                class_ref = f"{input_dataset}.{input_sheet}"
                class_names.append(class_ref)
                datasets_to_import.add(input_dataset)
                metadata[metadata_key] = class_ref
            else:
                # Same dataset or no dataset - use simple name (no import needed)
                class_names.append(input_sheet)
                metadata[metadata_key] = input_sheet

        return class_names, list(datasets_to_import), metadata

    def _auto_clean_names(self, dataset: str, sheet: str) -> tuple[str, str]:
        """Auto-clean both dataset and sheet names, log changes."""
        original_dataset, original_sheet = dataset, sheet

        clean_dataset = self._sanitize_dataset_name(dataset)
        clean_sheet = self._sanitize_sheet_name(sheet)

        # Log changes if any
        changes = []
        if original_dataset != clean_dataset:
            if clean_dataset is None:
                changes.append(f"dataset: '{original_dataset}' -> 'tasks/__init__.py'")
            else:
                changes.append(f"dataset: '{original_dataset}' -> '{clean_dataset}'")
        if original_sheet != clean_sheet:
            changes.append(f"sheet: '{original_sheet}' -> '{clean_sheet}'")

        if changes:
            logger.info(f"Auto-cleaned: {', '.join(changes)}")

        return clean_dataset, clean_sheet

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

            # Prepend data = self.inputLoad() to method code
            method_code_with_load = f"data = self.inputLoad()\n{method_code}"

            method_source = f"""    def {clean_method_name}(self):
{textwrap.indent(method_code_with_load, '        ')}"""
            methods.append(method_source)

        return "\n\n" + "\n\n".join(methods)

    def _validate_run_code(self, code: str) -> None:
        """Validate that run method code includes df_out assignment.

        Args:
            code: Run method code to validate

        Raises:
            ValueError: If df_out is not found in the code
        """
        if 'df_out' not in code:
            raise ValueError(
                "Run method code must assign results to 'df_out'. "
                "Example: df_out = pd.DataFrame({'data': [1, 2, 3]})"
            )

    def _generate_class_source(self, sheet: str, code: dict[str, str], inputs: list[str], inputs_metadata: dict[str, str] = None) -> str:
        """Generate source code for a sheet class.

        Args:
            sheet: Class name
            code: Dict of {method_name: method_code}. Must include 'run' key.
            inputs: List of input class references (e.g., ['sources.Hpi', 'Task2'])
            inputs_metadata: Optional dict mapping class reference to its actual reference (for decorator dict format)
        """
        decorator_str = ""
        if inputs:
            # Build decorator with metadata dict format: @d6tflow.requires({'sources.Hpi': sources.Hpi})
            decorator_items = [f"'{key}': {value}" for key, value in inputs_metadata.items()]
            decorator_dict = "{" + ", ".join(decorator_items) + "}"
            decorator_str = f"@d6tflow.requires({decorator_dict})\n"

        # Extract run method code and ensure it has self.save(df_out)
        if 'run' not in code:
            raise ValueError("code dict must include 'run' key")

        # Validate that run code includes df_out
        self._validate_run_code(code['run'])

        # Prepend data = self.inputLoad() to run code
        run_code_with_load = f"data = self.inputLoad()\n{code['run']}"
        run_code = self._ensure_save_statement(run_code_with_load)

        # Generate additional methods (all methods except 'run')
        other_methods = {k: v for k, v in code.items() if k != 'run'}
        additional_methods = self._generate_additional_methods(other_methods)

        class_source = f"""{decorator_str}class {sheet}(d6tflow.tasks.TaskPqPandas):
    def run(self):
{textwrap.indent(run_code, '        ')}{additional_methods}"""
        return class_source

    # ---------- Internal Helpers ----------
    
    def _prepare_sheet_operation(self, dataset: str, sheet: str):
        """Common preparation for sheet operations: clean names and get filename."""
        dataset, sheet = self._auto_clean_names(dataset, sheet)
        filename = self.get_filename(dataset)
        return dataset, sheet, filename
    
    def _get_dataset_display(self, dataset: str) -> str:
        """Get display name for dataset (tasks/__init__.py if None)."""
        return "tasks/__init__.py" if dataset is None else dataset

    def _get_file_display(self, dataset: str) -> str:
        """Get display name for file (tasks/__init__.py if None, else {dataset}.py)."""
        return "tasks/__init__.py" if dataset is None else f"{dataset}.py"

    # ---------- CRUD Methods ----------

    def create(self, sheet: str, code: dict[str, str], dataset: str = None, inputs: list[dict] | list[str] = None, imports: str = None):
        """Create a new sheet class (fails if already exists).

        Args:
            sheet: Class name
            code: Dict of {method_name: method_code}. Must include 'run' key.
            dataset: Dataset name (file to write to)
            inputs: List of input sheet dependencies. Can be:
                    - List of dicts: [{'dataset': 'sources', 'sheet': 'Hpi'}, ...]
                    - List of strings: ['Hpi', 'Another'] (legacy format)
            imports: Custom imports string
        """
        dataset_clean, sheet_clean, filename = self._prepare_sheet_operation(dataset, sheet)

        # Process inputs: validate, transform, and get datasets to import
        class_names, datasets_to_import, inputs_metadata = self._process_inputs(inputs, dataset_clean)

        # Load existing file or create new tree
        if filename.exists():
            tree = ast.parse(filename.read_text())
        else:
            tree = ast.parse("")

        # Ensure base imports first
        self._ensure_imports(tree)

        # Import required datasets from inputs
        for dataset_name in datasets_to_import:
            dataset_import = f"import {self.base_module}.{dataset_name}"
            self._merge_imports(tree, dataset_import)

        # Add custom imports if provided
        if imports:
            self._merge_imports(tree, imports)

        if self._find_class(tree, sheet_clean):
            raise ValueError(f"Class {sheet_clean} already exists in {dataset_clean}")

        class_source = self._generate_class_source(sheet_clean, code, class_names, inputs_metadata if inputs_metadata else None)
        class_ast = ast.parse(class_source)
        class_def = class_ast.body[0]

        tree.body.append(class_def)
        self._save_file(filename, tree)
        status_msg = f"Created {sheet_clean} in {self._get_dataset_display(dataset_clean)}"
        logger.success(status_msg)
        return status_msg

    def upsert(self, sheet: str, code: dict[str, str], dataset: str = None, inputs: list[dict] | list[str] = None, imports: str = None):
        """Create a new sheet class or update if it already exists (upsert).

        Args:
            sheet: Class name
            code: Dict of {method_name: method_code}. Must include 'run' key.
            dataset: Dataset name (file to write to)
            inputs: List of input sheet dependencies. Can be:
                    - List of dicts: [{'dataset': 'sources', 'sheet': 'Hpi'}, ...]
                    - List of strings: ['Hpi', 'Another'] (legacy format)
            imports: Custom imports string
        """
        dataset_clean, sheet_clean, filename = self._prepare_sheet_operation(dataset, sheet)

        # Check if sheet already exists
        if filename.exists():
            tree = ast.parse(filename.read_text())
            existing_class = self._find_class(tree, sheet_clean)
            if existing_class:
                # Update existing class
                return self.update(sheet=sheet_clean, dataset=dataset_clean, new_code=code, new_inputs=inputs, new_imports=imports)

        # Create new class
        return self.create(sheet=sheet_clean, code=code, dataset=dataset_clean, inputs=inputs, imports=imports)

    def upsert_run(self, sheet: str, code: str, dataset: str = None, inputs: list[dict] | list[str] = None, imports: str = None):
        """Convenience function to upsert just the run method.

        Args:
            sheet: Class name
            code: Code for the run() method (as string). Must assign results to 'df_out'.
                  Example: df_out = pd.DataFrame({'data': [1, 2, 3]})
            dataset: Dataset name (file to write to)
            inputs: List of input sheet dependencies
            imports: Custom imports string

        Raises:
            ValueError: If code does not include 'df_out' assignment
        """
        return self.upsert(sheet=sheet, code={'run': code}, dataset=dataset, inputs=inputs, imports=imports)

    def upsert_eda(self, sheet: str, code: str, dataset: str = None, inputs: list[dict] | list[str] = None, imports: str = None):
        """Convenience function to upsert just the eda method.

        Args:
            sheet: Class name
            code: Code for the eda() method (as string)
            dataset: Dataset name (file to write to)
            inputs: List of input sheet dependencies
            imports: Custom imports string
        """
        # Try to preserve the existing run method if sheet exists
        try:
            existing_run = self.read(sheet, dataset=dataset, method='run')
            return self.upsert(sheet=sheet, code={'run': existing_run, 'eda': code}, dataset=dataset, inputs=inputs, imports=imports)
        except ValueError:
            # Sheet doesn't exist yet, create with a default run method
            default_run = "df_out = None"
            return self.upsert(sheet=sheet, code={'run': default_run, 'eda': code}, dataset=dataset, inputs=inputs, imports=imports)

    def read(self, sheet: str, dataset: str = None, method: str = None) -> str:
        """Return the source code for a given class or specific method body.

        Args:
            sheet: Class name
            dataset: Dataset name (file to read from)
            method: Method name to read (e.g., 'run', 'eda'). If None, returns full class.

        Returns:
            Method body code if method specified, otherwise full class definition
        """
        dataset_clean, sheet_clean, filename = self._prepare_sheet_operation(dataset, sheet)

        if not filename.exists():
            raise ValueError(f"File {self._get_file_display(dataset_clean)} not found")

        tree = ast.parse(filename.read_text())
        cls = self._find_class(tree, sheet_clean)
        if not cls:
            raise ValueError(f"Class {sheet_clean} not found in {self._get_dataset_display(dataset_clean)}")

        if method:
            # Find and return specific method body
            for node in cls.body:
                if isinstance(node, ast.FunctionDef) and node.name == method:
                    # Return the method body as properly formatted code
                    body_code = []
                    for stmt in node.body:
                        body_code.append(ast.unparse(stmt))
                    code = '\n'.join(body_code)

                    # Strip the auto-added data = self.inputLoad() line if present
                    if code.startswith('data = self.inputLoad()\n'):
                        code = code[len('data = self.inputLoad()\n'):]

                    return code
            raise ValueError(f"{method}() method not found in {sheet_clean}")

        return ast.unparse(cls)

    def read_run(self, sheet: str, dataset: str = None) -> str:
        """Convenience function to read just the run method code.

        Args:
            sheet: Class name
            dataset: Dataset name (file to read from)

        Returns:
            Run method body code
        """
        return self.read(sheet, dataset=dataset, method='run')

    def update(
        self,
        sheet: str,
        dataset: str = None,
        new_code: dict[str, str] = None,
        new_inputs: list[dict] | list[str] = None,
        new_imports: str = None,
    ):
        """
        Update an existing class.

        Args:
            sheet: Class name
            new_code: Dict of {method_name: method_code} to replace. Can include 'run' and other methods.
            new_inputs: replace @d6tflow.requires(...). Can be:
                        - List of dicts: [{'dataset': 'sources', 'sheet': 'Hpi'}, ...]
                        - List of strings: ['Hpi', 'Another'] (legacy format)
            new_imports: add new imports to the file
        """
        dataset_clean, sheet_clean, filename = self._prepare_sheet_operation(dataset, sheet)

        # Process inputs if provided
        class_names = None
        inputs_metadata = None
        if new_inputs is not None:
            class_names, datasets_to_import, inputs_metadata = self._process_inputs(new_inputs, dataset_clean)

        if not filename.exists():
            raise ValueError(f"File {self._get_file_display(dataset_clean)} not found")

        tree = ast.parse(filename.read_text())
        cls = self._find_class(tree, sheet_clean)
        if not cls:
            raise ValueError(f"Class {sheet_clean} not found in {self._get_dataset_display(dataset_clean)}")

        # Import required datasets from inputs
        if new_inputs is not None:
            for dataset_name in datasets_to_import:
                dataset_import = f"import {self.base_module}.{dataset_name}"
                self._merge_imports(tree, dataset_import)

        # Add new imports if provided
        if new_imports:
            self._merge_imports(tree, new_imports)

        if new_code:
            # Handle 'run' method separately
            if 'run' in new_code:
                # Validate that run code includes df_out
                self._validate_run_code(new_code['run'])

                # Prepend data = self.inputLoad() to run code
                run_code_with_load = f"data = self.inputLoad()\n{new_code['run']}"
                run_code = self._ensure_save_statement(run_code_with_load)
                for node in cls.body:
                    if isinstance(node, ast.FunctionDef) and node.name == "run":
                        node.body = ast.parse(textwrap.dedent(run_code)).body
                        break
                else:
                    raise ValueError(f"run() not found in {sheet_clean}")

            # Handle other methods
            other_methods = {k: v for k, v in new_code.items() if k != 'run'}
            if other_methods:
                # Remove existing custom methods (keep only run, input, output, save)
                standard_methods = {'run', 'input', 'output', 'save'}
                cls.body = [
                    node for node in cls.body
                    if not (isinstance(node, ast.FunctionDef) and node.name not in standard_methods)
                ]

                # Add new methods
                for method_name, method_code in other_methods.items():
                    clean_method_name = self._sanitize_method_name(method_name)

                    # Prepend data = self.inputLoad() to method code
                    method_code_with_load = f"data = self.inputLoad()\n{method_code}"

                    # Create method AST
                    method_ast = ast.parse(f"""def {clean_method_name}(self):
{textwrap.indent(method_code_with_load, '    ')}""").body[0]

                    cls.body.append(method_ast)

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
            if class_names:
                # Build decorator string with metadata dict format
                decorator_items = [f"'{key}': {value}" for key, value in inputs_metadata.items()]
                decorator_dict = "{" + ", ".join(decorator_items) + "}"
                decorator_code = f"@d6tflow.requires({decorator_dict})"

                # Parse decorator and extract the Call node
                decorator_module = ast.parse(f"""
{decorator_code}
class Temp: pass
""")
                temp_class = decorator_module.body[0]
                decorator_ast = temp_class.decorator_list[0]
                cls.decorator_list.insert(0, decorator_ast)

        self._save_file(filename, tree)
        status_msg = f"Updated {sheet_clean} in {self._get_dataset_display(dataset_clean)}"
        logger.success(status_msg)
        return status_msg

    def delete(self, sheet: str, dataset: str = None):
        """Delete a class definition by sheet name."""
        dataset_clean, sheet_clean, filename = self._prepare_sheet_operation(dataset, sheet)
        
        if not filename.exists():
            raise ValueError(f"File {self._get_file_display(dataset_clean)} not found")
        
        tree = ast.parse(filename.read_text())
        new_body = [
            n
            for n in tree.body
            if not (isinstance(n, ast.ClassDef) and n.name == sheet_clean)
        ]
        if len(new_body) == len(tree.body):
            raise ValueError(f"Class {sheet_clean} not found in {self._get_dataset_display(dataset_clean)}")
        tree.body = new_body
        self._save_file(filename, tree)
        logger.success(f"Deleted {sheet_clean} from {self._get_dataset_display(dataset_clean)}")

    def list_sheets(self, dataset: str = None):
        """List all defined sheet class names in a specific dataset file."""
        original_dataset = dataset
        dataset = self._sanitize_dataset_name(dataset)
        if original_dataset != dataset:
            if dataset is None:
                logger.info(f"Auto-cleaned dataset: '{original_dataset}' -> 'tasks/__init__.py'")
            else:
                logger.info(f"Auto-cleaned dataset: '{original_dataset}' -> '{dataset}'")
        filename = self.get_filename(dataset)
        
        if not filename.exists():
            return []
        
        tree = ast.parse(filename.read_text())
        return [n.name for n in tree.body if isinstance(n, ast.ClassDef)]

    def list_datasets(self):
        """List all available datasets by scanning the base module directory."""
        if not self.base_module_dir.exists():
            return []
        
        modules = []
        for file_path in self.base_module_dir.iterdir():
            if file_path.is_file() and file_path.name.endswith(".py") and file_path.name != "__init__.py":
                # Extract dataset name from filename pattern: {dataset}.py
                module_name = file_path.name[:-3]  # Remove .py extension
                modules.append(module_name)
        
        return sorted(modules)

    def list_sheets_by_dataset(self, dataset: str = None):
        """List all sheet classes in a given dataset using AST parsing."""
        original_dataset = dataset
        dataset = self._sanitize_dataset_name(dataset)
        if original_dataset != dataset:
            if dataset is None:
                logger.info(f"Auto-cleaned dataset: '{original_dataset}' -> 'tasks/__init__.py'")
            else:
                logger.info(f"Auto-cleaned dataset: '{original_dataset}' -> '{dataset}'")
        filename = self.get_filename(dataset)
        
        if not filename.exists():
            return []
        
        tree = ast.parse(filename.read_text())
        return [n.name for n in tree.body if isinstance(n, ast.ClassDef)]

    def rename_sheet(self, old_sheet: str, new_sheet: str, dataset: str = None):
        """Rename a sheet class and update dependency references."""
        original_dataset, original_old_sheet, original_new_sheet = dataset, old_sheet, new_sheet

        dataset = self._sanitize_dataset_name(dataset)
        old_sheet = self._sanitize_sheet_name(old_sheet)
        new_sheet = self._sanitize_sheet_name(new_sheet)

        filename = self.get_filename(dataset)

        # Log changes
        changes = []
        if original_dataset != dataset:
            if dataset is None:
                changes.append(f"dataset: '{original_dataset}' -> 'tasks/__init__.py'")
            else:
                changes.append(f"dataset: '{original_dataset}' -> '{dataset}'")
        if original_old_sheet != old_sheet:
            changes.append(f"old sheet: '{original_old_sheet}' -> '{old_sheet}'")
        if original_new_sheet != new_sheet:
            changes.append(f"new sheet: '{original_new_sheet}' -> '{new_sheet}'")
        
        if changes:
            logger.info(f"Auto-cleaned: {', '.join(changes)}")
        
        if not filename.exists():
            raise ValueError(f"File {self._get_file_display(dataset_clean)} not found")
        
        tree = ast.parse(filename.read_text())
        cls = self._find_class(tree, old_sheet)
        if not cls:
            raise ValueError(f"Class {old_sheet} not found in {self._get_dataset_display(dataset_clean)}")
        if self._find_class(tree, new_sheet):
            raise ValueError(f"Class {new_sheet} already exists in {self._get_dataset_display(dataset_clean)}")

        # Rename class
        cls.name = new_sheet

        # Update all @d6tflow.requires(old_sheet) to new_sheet
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                for dec in node.decorator_list:
                    if (
                        isinstance(dec, ast.Call)
                        and isinstance(dec.func, ast.Attribute)
                        and dec.func.attr == "requires"
                    ):
                        for i, arg in enumerate(dec.args):
                            if isinstance(arg, ast.Name) and arg.id == old_sheet:
                                dec.args[i] = ast.Name(new_sheet, ast.Load())

        self._save_file(filename, tree)
        logger.success(f"Renamed {old_sheet} -> {new_sheet} in {self._get_dataset_display(dataset_clean)} and updated dependencies")

    # ---------- Flow Execution ----------

    def preview_flow(self, sheet: str, dataset: str = None,
                    flow_params: dict = None, reset_sheets: list[str] = None) -> str:
        """Generate and execute a preview script for a d6tflow workflow."""
        script = self.run_preview(sheet, dataset, flow_params, reset_sheets)
        return self.execute_preview(script)

    def _write_and_execute_script(self, script: str, file_out: str = None,
                                   execute: bool = False, script_type: str = "script") -> str | dict:
        """Helper method to write script to file and optionally execute it.

        Args:
            script: The script content to write
            file_out: File path to write the script to. Set to None to skip writing.
            execute: If True, execute the script after generating it. Requires file_out to be set.
            script_type: Description of script type for logging (e.g., "run", "preview", "task")

        Returns:
            If execute=True: dict with 'stdout', 'stderr', 'returncode' keys
            If file_out specified (no execute): str with file path written to
            Otherwise: the script content
        """
        if file_out:
            output_path = self.base_dir / file_out
            output_path.write_text(script)
            logger.info(f"Wrote {script_type} script to {output_path}")

            if execute:
                import subprocess
                import sys
                logger.info(f"Executing {output_path}")
                result = subprocess.run(
                    [sys.executable, str(output_path)],
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0:
                    logger.success(f"Successfully executed {output_path}")
                else:
                    logger.error(f"Execution failed with return code {result.returncode}")

                return {
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'returncode': result.returncode
                }
            else:
                return str(output_path)
        elif execute:
            raise ValueError("Cannot execute without file_out. Set file_out to a filename to execute.")

        return script

    def run_flow(self, sheet: str, dataset: str = None,
                  flow_params: dict = None, reset_sheets: list[str] = None,
                  file_out: str = "run_flow.py", execute: bool = False) -> str | dict:
        """Generate a run script for a d6tflow workflow.

        Args:
            sheet: Sheet name
            dataset: Dataset name
            flow_params: Flow parameters dict
            reset_sheets: List of sheets to reset
            file_out: File path to write the script to. Defaults to 'run_flow.py'. Set to None to skip writing.
            execute: If True, execute the script after generating it. Requires file_out to be set.

        Returns:
            If execute=True: dict with 'stdout', 'stderr', 'returncode' keys
            If file_out specified (no execute): str with file path written to
            Otherwise: the script content
        """
        script = self._generate_flow_script(sheet, dataset, flow_params, reset_sheets, preview_only=False)
        return self._write_and_execute_script(script, file_out, execute, "run")

    def run_preview(self, sheet: str, dataset: str = None,
                      flow_params: dict = None, reset_sheets: list[str] = None,
                      file_out: str = "run_preview.py", execute: bool = False) -> str | dict:
        """Generate a preview script for a d6tflow workflow.

        Args:
            sheet: Sheet name
            dataset: Dataset name
            flow_params: Flow parameters dict
            reset_sheets: List of sheets to reset
            file_out: File path to write the script to. Defaults to 'run_preview.py'. Set to None to skip writing.
            execute: If True, execute the script after generating it. Requires file_out to be set.

        Returns:
            If execute=True: dict with 'stdout', 'stderr', 'returncode' keys
            If file_out specified (no execute): str with file path written to
            Otherwise: the script content
        """
        script = self._generate_flow_script(sheet, dataset, flow_params, reset_sheets, preview_only=True)
        return self._write_and_execute_script(script, file_out, execute, "preview")

    def run_task(self, sheet: str, function: str, dataset: str = None,
                  file_out: str = "run_task.py", execute: bool = False) -> str | dict:
        """Generate a script to execute a specific function on a task class.

        Args:
            sheet: Sheet/Task class name
            function: Function name to execute on the task
            dataset: Dataset name (file to read from)
            file_out: File path to write the script to. Defaults to 'run_task.py'. Set to None to skip writing.
            execute: If True, execute the script after generating it. Requires file_out to be set.

        Returns:
            If execute=True: dict with 'stdout', 'stderr', 'returncode' keys
            If file_out specified (no execute): str with file path written to
            Otherwise: the script content
        """
        dataset_clean, sheet_clean = self._validate_flow_task(sheet, dataset)

        # Generate import statement
        if dataset_clean is None:
            import_line = f"import {self.base_module}"
            task_call = f"{self.base_module}.{sheet_clean}().{function}()"
        else:
            import_line = f"import {self.base_module}.{dataset_clean}"
            task_call = f"{self.base_module}.{dataset_clean}.{sheet_clean}().{function}()"

        # Generate script
        script = f"""import sys
import os
sys.path.insert(0, os.getcwd())

{import_line}

# {task_call}
{task_call}
"""

        return self._write_and_execute_script(script, file_out, execute, "task")

    def execute_run(self, script: str) -> str:
        """Execute a run script using subprocess."""
        return self._execute_script(script)

    def execute_preview(self, script: str) -> str:
        """Execute a preview script using subprocess."""
        return self._execute_script(script)

    def _validate_flow_task(self, sheet: str, dataset: str) -> tuple[str, str]:
        """Internal method to validate flow sheet exists."""
        # Reuse existing validation
        dataset_clean, sheet_clean, _ = self._prepare_sheet_operation(dataset, sheet)
        
        # Validate that the target sheet exists
        if dataset_clean is None:
            available_tasks = self.list_sheets()
        else:
            available_tasks = self.list_sheets(dataset_clean)
        
        if sheet_clean not in available_tasks:
            raise ValueError(f"Task {sheet_clean} not found in {self._get_dataset_display(dataset_clean)}")
        
        return dataset_clean, sheet_clean

    def _validate_reset_tasks(self, reset_tasks: list[str], target_dataset: str) -> list[str]:
        """Validate that reset sheets exist and return sanitized names."""
        if not reset_tasks:
            return []
        
        validated_tasks = []
        for reset_task in reset_tasks:
            # Sanitize sheet name
            clean_task = self._sanitize_sheet_name(reset_task)
            
            # Check if sheet exists in the target dataset
            if target_dataset is None:
                # Check in default dataset (tasks/__init__.py)
                available_tasks = self.list_sheets()
            else:
                # Check in specific dataset
                available_tasks = self.list_sheets(target_dataset)
            
            if clean_task not in available_tasks:
                logger.warning(f"Reset sheet '{reset_task}' (cleaned: '{clean_task}') not found in {self._get_dataset_display(target_dataset)}")
                # Continue anyway - d6tflow will handle the error
            
            validated_tasks.append(clean_task)
        
        return validated_tasks

    def _generate_flow_script(self, sheet: str, dataset: str, flow_params: dict, reset_sheets: list[str], preview_only: bool = False) -> str:
        """Generate the flow_run.py script content using string manipulation."""
        # Validate sheet exists
        dataset_clean, sheet_clean = self._validate_flow_task(sheet, dataset)

        # Validate reset_sheets exist
        reset_tasks = self._validate_reset_tasks(reset_sheets or [], dataset_clean)
        
        # Import section
        if dataset_clean is None:
            import_line = "import tasks"
            task_ref = f"tasks.{sheet_clean}"
        else:
            import_line = f"import tasks.{dataset_clean} as tasks"  
            task_ref = f"tasks.{sheet_clean}"
        
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
