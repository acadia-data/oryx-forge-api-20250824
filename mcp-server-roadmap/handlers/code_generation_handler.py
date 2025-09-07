"""
Handles code generation operations using OryxForge.
Provides tools for creating data processing workflows.
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, List
from mcp.types import Tool, TextContent

# Add the parent directory to sys.path to import oryxforge
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from oryxforge.services.task_service import TaskService
except ImportError:
    # Fallback for when oryxforge is not available
    TaskService = None

class CodeGenerationHandler:
    """Handles code generation using OryxForge library."""
    
    def __init__(self, output_directory: str = "generated_workflows"):
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(exist_ok=True)
        
        if TaskService is None:
            raise ImportError("OryxForge TaskService not available. Please ensure oryxforge is installed.")
    
    def get_tools(self) -> List[Tool]:
        """Returns the tools this handler provides."""
        return [
            Tool(
                name="create_data_task",
                description="Create a new data processing task",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task_name": {
                            "type": "string",
                            "description": "Name of the task to create"
                        },
                        "code": {
                            "type": "string", 
                            "description": "Python code for the task's run() method"
                        },
                        "dependencies": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of task dependencies"
                        },
                        "workflow_name": {
                            "type": "string",
                            "description": "Name of the workflow file",
                            "default": "default_workflow"
                        }
                    },
                    "required": ["task_name", "code"]
                }
            ),
            Tool(
                name="update_data_task",
                description="Update an existing data processing task",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task_name": {
                            "type": "string",
                            "description": "Name of the task to update"
                        },
                        "code": {
                            "type": "string", 
                            "description": "New Python code for the task's run() method"
                        },
                        "dependencies": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "New list of task dependencies"
                        },
                        "workflow_name": {
                            "type": "string",
                            "description": "Name of the workflow file",
                            "default": "default_workflow"
                        }
                    },
                    "required": ["task_name", "code"]
                }
            ),
            Tool(
                name="list_tasks",
                description="List all tasks in a workflow",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "workflow_name": {
                            "type": "string",
                            "description": "Name of the workflow",
                            "default": "default_workflow"
                        }
                    }
                }
            ),
            Tool(
                name="delete_task",
                description="Delete a task from a workflow",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task_name": {
                            "type": "string",
                            "description": "Name of the task to delete"
                        },
                        "workflow_name": {
                            "type": "string",
                            "description": "Name of the workflow file",
                            "default": "default_workflow"
                        }
                    },
                    "required": ["task_name"]
                }
            ),
            Tool(
                name="generate_workflow_code",
                description="Generate complete workflow code",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "workflow_name": {
                            "type": "string",
                            "description": "Name of the workflow to generate",
                            "default": "default_workflow"
                        }
                    }
                }
            ),
            Tool(
                name="read_task_code",
                description="Read the code for a specific task",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task_name": {
                            "type": "string",
                            "description": "Name of the task to read"
                        },
                        "workflow_name": {
                            "type": "string",
                            "description": "Name of the workflow file",
                            "default": "default_workflow"
                        }
                    },
                    "required": ["task_name"]
                }
            ),
            Tool(
                name="rename_task",
                description="Rename a task and update all references",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "old_name": {
                            "type": "string",
                            "description": "Current name of the task"
                        },
                        "new_name": {
                            "type": "string",
                            "description": "New name for the task"
                        },
                        "workflow_name": {
                            "type": "string",
                            "description": "Name of the workflow file",
                            "default": "default_workflow"
                        }
                    },
                    "required": ["old_name", "new_name"]
                }
            )
        ]
    
    async def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        """Handle tool calls for code generation."""
        
        if tool_name == "create_data_task":
            return await self._create_data_task(
                arguments["task_name"],
                arguments["code"],
                arguments.get("dependencies", []),
                arguments.get("workflow_name", "default_workflow")
            )
        elif tool_name == "update_data_task":
            return await self._update_data_task(
                arguments["task_name"],
                arguments["code"],
                arguments.get("dependencies"),
                arguments.get("workflow_name", "default_workflow")
            )
        elif tool_name == "list_tasks":
            return await self._list_tasks(
                arguments.get("workflow_name", "default_workflow")
            )
        elif tool_name == "delete_task":
            return await self._delete_task(
                arguments["task_name"],
                arguments.get("workflow_name", "default_workflow")
            )
        elif tool_name == "generate_workflow_code":
            return await self._generate_workflow_code(
                arguments.get("workflow_name", "default_workflow")
            )
        elif tool_name == "read_task_code":
            return await self._read_task_code(
                arguments["task_name"],
                arguments.get("workflow_name", "default_workflow")
            )
        elif tool_name == "rename_task":
            return await self._rename_task(
                arguments["old_name"],
                arguments["new_name"],
                arguments.get("workflow_name", "default_workflow")
            )
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    
    async def _create_data_task(self, task_name: str, code: str, dependencies: List[str], workflow_name: str) -> List[TextContent]:
        """Create a new data processing task."""
        try:
            workflow_path = self.output_directory / f"{workflow_name}.py"
            task_service = TaskService(str(workflow_path))
            
            task_service.create(task_name, code, dependencies)
            
            return [TextContent(
                type="text",
                text=f"✅ Created task '{task_name}' in workflow '{workflow_name}'\nDependencies: {dependencies or 'None'}\nCode:\n```python\n{code}\n```"
            )]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error creating task '{task_name}': {str(e)}"
            )]
    
    async def _update_data_task(self, task_name: str, code: str, dependencies: List[str], workflow_name: str) -> List[TextContent]:
        """Update an existing data processing task."""
        try:
            workflow_path = self.output_directory / f"{workflow_name}.py"
            task_service = TaskService(str(workflow_path))
            
            if dependencies is not None:
                task_service.update(task_name, new_code=code, new_dependencies=dependencies)
            else:
                task_service.update(task_name, new_code=code)
            
            return [TextContent(
                type="text",
                text=f"✅ Updated task '{task_name}' in workflow '{workflow_name}'\nNew code:\n```python\n{code}\n```"
            )]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error updating task '{task_name}': {str(e)}"
            )]
    
    async def _list_tasks(self, workflow_name: str) -> List[TextContent]:
        """List all tasks in a workflow."""
        try:
            workflow_path = self.output_directory / f"{workflow_name}.py"
            
            if not workflow_path.exists():
                return [TextContent(
                    type="text",
                    text=f"Workflow '{workflow_name}' not found"
                )]
            
            task_service = TaskService(str(workflow_path))
            tasks = task_service.list_tasks()
            
            if not tasks:
                return [TextContent(
                    type="text",
                    text=f"No tasks found in workflow '{workflow_name}'"
                )]
            
            task_list = "\n".join(f"- {task}" for task in tasks)
            return [TextContent(
                type="text",
                text=f"Tasks in workflow '{workflow_name}':\n{task_list}"
            )]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error listing tasks: {str(e)}"
            )]
    
    async def _delete_task(self, task_name: str, workflow_name: str) -> List[TextContent]:
        """Delete a task from a workflow."""
        try:
            workflow_path = self.output_directory / f"{workflow_name}.py"
            task_service = TaskService(str(workflow_path))
            
            task_service.delete(task_name)
            
            return [TextContent(
                type="text",
                text=f"✅ Deleted task '{task_name}' from workflow '{workflow_name}'"
            )]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error deleting task '{task_name}': {str(e)}"
            )]
    
    async def _generate_workflow_code(self, workflow_name: str) -> List[TextContent]:
        """Generate complete workflow code."""
        try:
            workflow_path = self.output_directory / f"{workflow_name}.py"
            
            if not workflow_path.exists():
                return [TextContent(
                    type="text",
                    text=f"Workflow '{workflow_name}' not found"
                )]
            
            code = workflow_path.read_text()
            return [TextContent(
                type="text",
                text=f"Generated workflow code for '{workflow_name}':\n\n```python\n{code}\n```"
            )]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error generating workflow code: {str(e)}"
            )]
    
    async def _read_task_code(self, task_name: str, workflow_name: str) -> List[TextContent]:
        """Read the code for a specific task."""
        try:
            workflow_path = self.output_directory / f"{workflow_name}.py"
            task_service = TaskService(str(workflow_path))
            
            code = task_service.read(task_name)
            
            return [TextContent(
                type="text",
                text=f"Code for task '{task_name}' in workflow '{workflow_name}':\n\n```python\n{code}\n```"
            )]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error reading task '{task_name}': {str(e)}"
            )]
    
    async def _rename_task(self, old_name: str, new_name: str, workflow_name: str) -> List[TextContent]:
        """Rename a task and update all references."""
        try:
            workflow_path = self.output_directory / f"{workflow_name}.py"
            task_service = TaskService(str(workflow_path))
            
            task_service.rename(old_name, new_name)
            
            return [TextContent(
                type="text",
                text=f"✅ Renamed task '{old_name}' to '{new_name}' in workflow '{workflow_name}' and updated all dependencies"
            )]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error renaming task '{old_name}' to '{new_name}': {str(e)}"
            )]
