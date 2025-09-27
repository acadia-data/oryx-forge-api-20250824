"""MCP tools for WorkflowService CRUD operations."""

import os
from pathlib import Path
from typing import Any
from mcp.server.fastmcp import FastMCP
from oryxforge.services.workflow_service import WorkflowService

# Initialize the workflow service with current working directory
svc = WorkflowService(base_dir=str(Path.cwd()))

# Create FastMCP instance
mcp = FastMCP("OryxForge")


@mcp.tool
def create_sheet(dataset: str, sheet: str, code: str, dependencies: list[str] = None) -> str:
    """Create a new sheet class in the specified dataset."""
    if dependencies is None:
        dependencies = []
    svc.create(sheet, code, dataset, dependencies)
    return f"Created sheet {sheet} in dataset {dataset}"


@mcp.tool
def read_sheet(dataset: str, sheet: str) -> str:
    """Read the source code of a sheet class."""
    return svc.read(sheet, dataset)


@mcp.tool
def update_sheet(dataset: str, sheet: str, new_code: str = None, new_dependencies: list[str] = None) -> str:
    """Update an existing sheet class."""
    svc.update(sheet, dataset, new_code, new_dependencies)
    return f"Updated sheet {sheet} in dataset {dataset}"


@mcp.tool
def delete_sheet(dataset: str, sheet: str) -> str:
    """Delete a sheet class from a dataset."""
    svc.delete(sheet, dataset)
    return f"Deleted sheet {sheet} from dataset {dataset}"


@mcp.tool
def upsert_sheet(dataset: str, sheet: str, code: str, dependencies: list[str] = None) -> str:
    """Create a new sheet class or update if it already exists."""
    if dependencies is None:
        dependencies = []
    svc.upsert(sheet, code, dataset, dependencies)
    return f"Upserted sheet {sheet} in dataset {dataset}"


@mcp.tool
def list_sheets(dataset: str) -> list[str]:
    """List all sheet classes in a specific dataset."""
    return svc.list_sheets(dataset)


@mcp.tool
def list_datasets() -> list[str]:
    """List all available datasets."""
    return svc.list_datasets()


@mcp.tool
def list_sheets_by_dataset(dataset: str) -> list[str]:
    """List all sheet classes in a given dataset."""
    return svc.list_sheets_by_dataset(dataset)


@mcp.tool
def rename_sheet(dataset: str, old_sheet: str, new_sheet: str) -> str:
    """Rename a sheet class and update dependency references."""
    svc.rename_sheet(old_sheet, new_sheet, dataset)
    return f"Renamed sheet {old_sheet} to {new_sheet} in dataset {dataset}"


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
def list_directory(path: str = ".") -> list[str]:
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


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')
