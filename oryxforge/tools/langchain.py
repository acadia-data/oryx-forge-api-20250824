"""LangChain tools for WorkflowService and ProjectService operations."""

from pathlib import Path
from typing import Optional
from langchain.tools import tool
from oryxforge.services.workflow_service import WorkflowService
from oryxforge.services.project_service import ProjectService
from oryxforge.services.utils import get_user_id, get_project_id

# Initialize the workflow service with current working directory
svc = WorkflowService(base_dir=str(Path.cwd()))


# Code management functions
@tool
def code_upsert_eda(sheet: str, code: str, dataset: Optional[str] = None, inputs: Optional[list[dict]] = None, imports: Optional[str] = None) -> str:
    """Create or update the eda method of a sheet class."""
    if inputs is None:
        inputs = []
    return svc.upsert_eda(sheet, code, dataset, inputs, imports)


@tool
def code_read_eda(sheet: str, dataset: Optional[str] = None) -> str:
    """Read the eda method code of a sheet class."""
    return svc.read(sheet, dataset, method='eda')


@tool
def code_upsert_run(sheet: str, code: str, dataset: Optional[str] = None, inputs: Optional[list[dict]] = None, imports: Optional[str] = None) -> str:
    """Create or update the run method of a sheet class."""
    if inputs is None:
        inputs = []
    return svc.upsert_run(sheet, code, dataset, inputs, imports)


@tool
def code_read_run(sheet: str, dataset: Optional[str] = None) -> str:
    """Read the run method code of a sheet class."""
    return svc.read(sheet, dataset, method='run')


# Workflow execution functions
@tool
def workflow_run_eda(sheet: str, dataset: Optional[str] = None) -> dict:
    """Execute the eda method of a sheet class."""
    return svc.run_task(sheet, 'eda', dataset=dataset, execute=True)


@tool
def workflow_run_flow(sheet: str, dataset: Optional[str] = None, flow_params: Optional[dict] = None, reset_sheets: Optional[list[str]] = None) -> dict:
    """Execute a d6tflow workflow for a sheet class."""
    return svc.run_flow(sheet, dataset, flow_params=flow_params, reset_sheets=reset_sheets, execute=True)


# Project management functions
@tool
def project_create_dataset(name: str) -> str:
    """Create a new dataset in the current project."""
    user_id = get_user_id()
    project_id = get_project_id()
    project_service = ProjectService(project_id, user_id)
    return project_service.ds_create(name)


@tool
def project_create_sheet(dataset_id: str, name: str) -> str:
    """Create a new datasheet in the specified dataset."""
    user_id = get_user_id()
    project_id = get_project_id()
    project_service = ProjectService(project_id, user_id)
    return project_service.sheet_create(dataset_id, name)


@tool
def project_list_datasets() -> list[dict]:
    """List all datasets in the current project."""
    user_id = get_user_id()
    project_id = get_project_id()
    project_service = ProjectService(project_id, user_id)
    return project_service.ds_list()


@tool
def project_list_sheets(dataset_id: Optional[str] = None) -> list[dict]:
    """List all datasheets in the current project or specific dataset."""
    user_id = get_user_id()
    project_id = get_project_id()
    project_service = ProjectService(project_id, user_id)
    return project_service.sheet_list(dataset_id)


# Export all tools as a list for easy import
TOOLS = [
    code_upsert_eda,
    code_read_eda,
    code_upsert_run,
    code_read_run,
    workflow_run_eda,
    workflow_run_flow,
    project_create_dataset,
    project_create_sheet,
    project_list_datasets,
    project_list_sheets,
]