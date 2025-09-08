"""MCP tools for TaskService CRUD operations."""

import os
from pathlib import Path
from typing import Any
from fastmcp import FastMCP
from oryxforge.services.task_service import TaskService

# Initialize the task service with current working directory
svc = TaskService(base_dir=str(Path.cwd()))

# Create FastMCP instance
mcp = FastMCP("OryxForge")


@mcp.tool
def create_task(task: str, code: str, module: str = None, inputs: list[str] = None) -> str:
    """Create a new task class in the specified module."""
    if inputs is None:
        inputs = []
    svc.create(task, code, module, inputs)
    return f"Created task {task} in module {module if module else 'tasks/__init__.py'}"


@mcp.tool
def read_task(task: str, module: str = None) -> str:
    """Read the source code of a task class."""
    return svc.read(task, module)


@mcp.tool
def update_task(task: str, module: str = None, new_code: str = None, new_inputs: list[str] = None) -> str:
    """Update an existing task class."""
    svc.update(task, module, new_code, new_inputs)
    return f"Updated task {task} in module {module if module else 'tasks/__init__.py'}"


@mcp.tool
def delete_task(task: str, module: str = None) -> str:
    """Delete a task class from a module."""
    svc.delete(task, module)
    return f"Deleted task {task} from module {module if module else 'tasks/__init__.py'}"


@mcp.tool
def upsert_task(task: str, code: str, module: str = None, inputs: list[str] = None) -> str:
    """Create a new task class or update if it already exists."""
    if inputs is None:
        inputs = []
    svc.upsert(task, code, module, inputs)
    return f"Upserted task {task} in module {module if module else 'tasks/__init__.py'}"


@mcp.tool
def list_tasks(module: str = None) -> list[str]:
    """List all task classes in a specific module."""
    return svc.list_tasks(module)


@mcp.tool
def list_modules() -> list[str]:
    """List all available task modules."""
    return svc.list_modules()


@mcp.tool
def list_tasks_by_module(module: str = None) -> list[str]:
    """List all task classes in a given module."""
    return svc.list_tasks_by_module(module)


@mcp.tool
def rename_task(old_task: str, new_task: str, module: str = None) -> str:
    """Rename a task class and update input references."""
    svc.rename_task(old_task, new_task, module)
    return f"Renamed task {old_task} to {new_task} in module {module if module else 'tasks/__init__.py'}"


@mcp.tool
def get_working_directory() -> str:
    """Get the current working directory of the task service."""
    return str(svc.base_dir)


@mcp.tool
def get_tasks_directory() -> str:
    """Get the tasks directory path."""
    return str(svc.base_module_dir)


@mcp.tool
def change_working_directory(path: str) -> str:
    """Change the working directory for the task service."""
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
        
        # Reinitialize the task service with the new directory
        svc = TaskService(base_dir=str(new_path))
        
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