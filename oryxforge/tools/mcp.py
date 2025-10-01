"""MCP tools for WorkflowService and ProjectService operations."""

import os
from pathlib import Path
from typing import Any, Optional
from fastmcp import FastMCP
from oryxforge.services.workflow_service import WorkflowService
from oryxforge.services.project_service import ProjectService
from oryxforge.services.utils import get_user_id, get_project_id

# Initialize the workflow service with current working directory
svc = WorkflowService(base_dir=str(Path.cwd()))

# Create FastMCP instance
mcp = FastMCP("OryxForge")



def utest0():
    """just teset it"""
    # {
    #   "cwd": "D:\\OneDrive\\dev\\oryx-forge\\oryx-forge-template-20250923"
    # }
    # r = svc.run_task('fileimport', 'eda', dataset='explore', execute=False)#, file_out=None)
    # output_path = 'run_task.py'
    # D:\OneDrive\dev\oryx-forge\oryx-forge-template-20250923\run_task.py

    try:
        import subprocess
        import sys
        result = subprocess.run(
            ['python', '-c', "print(1)"],
            capture_output=True,
            text=True)

        return {
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode
        }
    except:
        return f"Error executing command"

def utest1():
    return 'hello world'

async def utest():
    """Test async subprocess execution."""
    import asyncio
    import sys

    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable, '-c', 'print(1)',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        return {
            'stdout': stdout.decode() if stdout else '',
            'stderr': stderr.decode() if stderr else '',
            'returncode': process.returncode
        }
    except Exception as e:
        return f"Error executing command: {str(e)}"


# Code management functions
def code_upsert_eda(sheet: str, code: str, dataset: Optional[str] = None, inputs: Optional[list[str]] = None, imports: Optional[str] = None) -> str:
    """Create or update the eda method of a sheet class."""
    if inputs is None:
        inputs = []
    return svc.upsert_eda(sheet, code, dataset, inputs, imports)


def code_read_eda(sheet: str, dataset: Optional[str] = None) -> str:
    """Read the eda method code of a sheet class."""
    return svc.read(sheet, dataset, method='eda')


def code_upsert_run(sheet: str, code: str, dataset: Optional[str] = None, inputs: Optional[list[str]] = None, imports: Optional[str] = None) -> str:
    """Create or update the run method of a sheet class."""
    if inputs is None:
        inputs = []
    return svc.upsert_run(sheet, code, dataset, inputs, imports)


def code_read_run(sheet: str, dataset: Optional[str] = None) -> str:
    """Read the run method code of a sheet class."""
    return svc.read(sheet, dataset, method='run')


# Workflow execution functions
def workflow_run_eda(sheet: str, dataset: Optional[str] = None) -> dict:
    """Execute the eda method of a sheet class."""
    return svc.run_task(sheet, 'eda', dataset=dataset, execute=True)


def workflow_run_flow(sheet: str, dataset: Optional[str] = None, flow_params: Optional[dict] = None, reset_sheets: Optional[list[str]] = None) -> dict:
    """Execute a d6tflow workflow for a sheet class."""
    return svc.run_flow(sheet, dataset, flow_params=flow_params, reset_sheets=reset_sheets, execute=True)


# Project management functions
def project_create_dataset(name: str) -> str:
    """Create a new dataset in the current project."""
    user_id = get_user_id()
    project_id = get_project_id()
    project_service = ProjectService(project_id, user_id)
    return project_service.ds_create(name)


def project_create_sheet(dataset_id: str, name: str) -> str:
    """Create a new datasheet in the specified dataset."""
    user_id = get_user_id()
    project_id = get_project_id()
    project_service = ProjectService(project_id, user_id)
    return project_service.sheet_create(dataset_id, name)


def project_list_datasets() -> list[dict]:
    """List all datasets in the current project."""
    user_id = get_user_id()
    project_id = get_project_id()
    project_service = ProjectService(project_id, user_id)
    return project_service.ds_list()


def project_list_sheets(dataset_id: Optional[str] = None) -> list[dict]:
    """List all datasheets in the current project or specific dataset."""
    user_id = get_user_id()
    project_id = get_project_id()
    project_service = ProjectService(project_id, user_id)
    return project_service.sheet_list(dataset_id)


# Register all tools with MCP
mcp.tool(utest)
mcp.tool(utest1)
mcp.tool(code_upsert_eda)
mcp.tool(code_read_eda)
mcp.tool(code_upsert_run)
mcp.tool(code_read_run)
mcp.tool(workflow_run_eda)
mcp.tool(workflow_run_flow)
mcp.tool(project_create_dataset)
mcp.tool(project_create_sheet)
mcp.tool(project_list_datasets)
mcp.tool(project_list_sheets)
