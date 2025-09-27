"""MCP tools for WorkflowService CRUD operations."""

import os
from pathlib import Path
from typing import Any, Optional
from fastmcp import FastMCP
from oryxforge.services.workflow_service import WorkflowService

# Initialize the workflow service with current working directory
svc = WorkflowService(base_dir=str(Path.cwd()))

# Create FastMCP instance
mcp = FastMCP("OryxForge")


@mcp.tool
def create_sheet(sheet: str, code: str, dataset: Optional[str] = None, inputs: Optional[list[str]] = None, imports: Optional[str] = None) -> str:
    """Create a new sheet class in the specified dataset."""
    if inputs is None:
        inputs = []
    return svc.create(sheet, code, dataset, inputs, imports)


@mcp.tool
def read_sheet(sheet: str, dataset: Optional[str] = None) -> str:
    """Read the source code of a sheet class."""
    return svc.read(sheet, dataset)


@mcp.tool
def update_sheet(sheet: str, dataset: Optional[str] = None, new_code: Optional[str] = None, new_inputs: Optional[list[str]] = None, new_imports: Optional[str] = None) -> str:
    """Update an existing sheet class."""
    return svc.update(sheet, dataset, new_code, new_inputs, new_imports)


@mcp.tool
def delete_sheet(sheet: str, dataset: Optional[str] = None) -> str:
    """Delete a sheet class from a dataset."""
    svc.delete(sheet, dataset)
    return f"Deleted sheet {sheet} from dataset {dataset if dataset else 'tasks/__init__.py'}"


@mcp.tool
def upsert_sheet(sheet: str, code: str, dataset: Optional[str] = None, inputs: Optional[list[str]] = None, imports: Optional[str] = None) -> str:
    """Create a new sheet class or update if it already exists."""
    if inputs is None:
        inputs = []
    return svc.upsert(sheet, code, dataset, inputs, imports)


@mcp.tool
def list_sheets(dataset: Optional[str] = None) -> list[str]:
    """List all sheet classes in a specific dataset."""
    return svc.list_sheets(dataset)


@mcp.tool
def list_datasets() -> list[str]:
    """List all available datasets."""
    return svc.list_datasets()


@mcp.tool
def list_sheets_by_dataset(dataset: Optional[str] = None) -> list[str]:
    """List all sheet classes in a given dataset."""
    return svc.list_sheets_by_dataset(dataset)


@mcp.tool
def rename_sheet(old_sheet: str, new_sheet: str, dataset: Optional[str] = None) -> str:
    """Rename a sheet class and update input references."""
    svc.rename_sheet(old_sheet, new_sheet, dataset)
    return f"Renamed sheet {old_sheet} to {new_sheet} in dataset {dataset if dataset else 'tasks/__init__.py'}"


@mcp.tool
def get_working_directory() -> str:
    """Get the current working directory of the workflow service."""
    return str(svc.base_dir)


@mcp.tool
def get_tasks_directory() -> str:
    """Get the tasks directory path."""
    return str(svc.base_module_dir)


@mcp.tool
def change_working_directory(path: str) -> str:
    """Change the working directory for the workflow service."""
    global svc
    try:
        # Expand user path and make absolute
        new_path = Path(path).expanduser().resolve()
        
        # Verify the directory exists
        if not new_path.exists():
            return f"Error: Directory does not exist: {new_path}"
        
        if not new_path.is_dir():
            return f"Error: Path is not a directory: {new_path}"
        
        # Change OS working directory
        os.chdir(new_path)
        
        # Reinitialize the workflow service with the new directory
        svc = WorkflowService(base_dir=str(new_path))
        
        return f"Changed working directory to: {new_path}"
    
    except PermissionError:
        return f"Error: Permission denied accessing: {path}"
    except Exception as e:
        return f"Error changing directory: {str(e)}"


@mcp.tool
def list_directory(path: Optional[str] = ".") -> list[str]:
    """List contents of a directory (default: current directory)."""
    try:
        dir_path = Path(path).expanduser().resolve()
        if not dir_path.exists():
            return [f"Error: Directory does not exist: {dir_path}"]
        
        if not dir_path.is_dir():
            return [f"Error: Path is not a directory: {dir_path}"]
        
        contents = []
        for item in sorted(dir_path.iterdir()):
            if item.is_dir():
                contents.append(f"{item.name}/")
            else:
                contents.append(item.name)
        
        return contents
    
    except PermissionError:
        return [f"Error: Permission denied accessing: {path}"]
    except Exception as e:
        return [f"Error listing directory: {str(e)}"]


@mcp.tool
def create_run(sheet: str, dataset: Optional[str] = None,
              flow_params: Optional[dict] = None,
              reset_sheets: Optional[list[str]] = None) -> str:
    """Generate a run script for a d6tflow workflow."""
    return svc.create_run(sheet, dataset, flow_params, reset_sheets)


@mcp.tool
def create_preview(sheet: str, dataset: Optional[str] = None,
                  flow_params: Optional[dict] = None,
                  reset_sheets: Optional[list[str]] = None) -> str:
    """Generate a preview script for a d6tflow workflow."""
    return svc.create_preview(sheet, dataset, flow_params, reset_sheets)


@mcp.tool
def execute_run(script: str) -> str:
    """Execute a run script using subprocess."""
    return svc.execute_run(script)


@mcp.tool
def execute_preview(script: str) -> str:
    """Execute a preview script using subprocess."""
    return svc.execute_preview(script)


@mcp.tool
def preview_flow(sheet: str, dataset: Optional[str] = None,
                flow_params: Optional[dict] = None,
                reset_sheets: Optional[list[str]] = None) -> str:
    """Generate and execute a preview script for a d6tflow workflow."""
    return svc.preview_flow(sheet, dataset, flow_params, reset_sheets)