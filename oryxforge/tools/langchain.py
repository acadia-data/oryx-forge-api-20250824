"""LangChain tools for WorkflowService and ProjectService operations."""

from pathlib import Path
from typing import Optional
import pandas as pd
from langchain.tools import tool
from oryxforge.services.workflow_service import WorkflowService
from oryxforge.services.project_service import ProjectService
from oryxforge.services.df_service import DFService

# Initialize services with current working directory
svc = WorkflowService(base_dir=str(Path.cwd()))
df_svc = DFService()


# Code management functions
@tool
def code_upsert_eda(sheet: str, code: str, dataset: Optional[str] = None, inputs: Optional[list[dict]] = None, imports: Optional[str] = None) -> dict[str, str]:
    """Create or update the eda (exploratory data analysis) method of a sheet class.

    Args:
        sheet: The name_python of the datasheet to update
        code: The Python code for the eda method body
        dataset: The name_python of the dataset (optional, uses default if None)
        inputs: List of upstream dependencies as dicts: [{'dataset': 'sources', 'sheet': 'HpiMasterCsv'}, ...]
        imports: Additional Python import statements to add to the sheet class

    Returns:
        Dict with 'status' (success message) and 'file_python_eda' (path to generated script)
    """
    if inputs is None:
        inputs = []
    status = svc.upsert_eda(sheet, code, dataset, inputs, imports)
    file = svc.run_task(sheet, 'eda', dataset=dataset, execute=False)
    return {'status': status, 'file_python_eda': file}


@tool
def code_read_eda(sheet: str, dataset: Optional[str] = None) -> str:
    """Read the current eda method code of a sheet class.

    Args:
        sheet: The name_python of the datasheet to read
        dataset: The name_python of the dataset (optional, uses default if None)

    Returns:
        The Python code of the eda method as a string
    """
    return svc.read(sheet, dataset, method='eda')


@tool
def code_upsert_run(sheet: str, code: str, dataset: Optional[str] = None, inputs: Optional[list[dict]] = None, imports: Optional[str] = None) -> dict[str, str]:
    """Create or update the run method of a sheet class for d6tflow workflow execution.

    Args:
        sheet: The name_python of the datasheet to update
        code: The Python code for the run method body
        dataset: The name_python of the dataset (optional, uses default if None)
        inputs: List of upstream dependencies as dicts: [{'dataset': 'sources', 'sheet': 'HpiMasterCsv'}, ...]
        imports: Additional Python import statements to add to the sheet class

    Returns:
        Dict with 'status' (success message) and 'file_python_flow' (path to generated workflow script)
    """
    if inputs is None:
        inputs = []
    status = svc.upsert_run(sheet, code, dataset, inputs, imports)
    file = svc.run_flow(sheet, dataset, execute=False)
    return {'status': status, 'file_python_flow': file}


@tool
def code_read_run(sheet: str, dataset: Optional[str] = None) -> str:
    """Read the current run method code of a sheet class.

    Args:
        sheet: The name_python of the datasheet to read
        dataset: The name_python of the dataset (optional, uses default if None)

    Returns:
        The Python code of the run method as a string
    """
    return svc.read(sheet, dataset, method='run')


# Workflow execution functions
@tool
def workflow_run_eda(sheet: str, dataset: Optional[str] = None) -> dict:
    """Generate and return the Python script to execute the eda method of a sheet class.

    Args:
        sheet: The name_python of the datasheet to execute
        dataset: The name_python of the dataset (optional, uses default if None)

    Returns:
        Dict with 'file_python_eda' key containing path to generated Python script
    """
    file = svc.run_task(sheet, 'eda', dataset=dataset, execute=False)
    return {'file_python_eda': file}


@tool
def workflow_run_flow(sheet: str, dataset: Optional[str] = None, flow_params: Optional[dict] = None, reset_sheets: Optional[list[str]] = None) -> dict:
    """Generate and return the Python script to execute a d6tflow workflow for a sheet class.

    Args:
        sheet: The name_python of the datasheet to execute
        dataset: The name_python of the dataset (optional, uses default if None)
        flow_params: Optional parameters to pass to the workflow execution
        reset_sheets: List of sheet names to reset before execution
                     Example: ['HpiMasterCsv', 'CleanedData']
                     Note: These should be simple sheet names from the same dataset

    Returns:
        Dict with 'file_python_flow' key containing path to generated Python workflow script
    """
    file = svc.run_flow(sheet, dataset, flow_params=flow_params, reset_sheets=reset_sheets, reset_task=True, execute=False)
    return {'file_python_flow': file}


# Project management functions
@tool
def project_create_dataset(name: str) -> str:
    """Create a new dataset in the current project.

    Uses profile from .oryxforge configuration to get user_id and project_id.

    Args:
        name: The display name for the new dataset (will be converted to name_python internally)

    Returns:
        The ID of the newly created dataset
    """
    project_service = ProjectService()
    return project_service.ds_create(name)


@tool
def project_create_sheet(dataset_id: str, name: str) -> str:
    """Create a new datasheet in the specified dataset.

    Uses profile from .oryxforge configuration to get user_id and project_id.

    Args:
        dataset_id: The ID of the dataset to create the sheet in
        name: The display name for the new datasheet (will be converted to name_python internally)

    Returns:
        The ID of the newly created datasheet
    """
    project_service = ProjectService()
    sheet_data = project_service.sheet_create(dataset_id, name)
    return sheet_data['id']


@tool
def project_list_datasets() -> list[dict]:
    """List all datasets in the current project.

    Uses profile from .oryxforge configuration to get user_id and project_id.

    Returns:
        List of dicts, each containing id, name, and name_python fields for a dataset
    """
    project_service = ProjectService()
    return project_service.ds_list()


@tool
def project_get_dataset(id: Optional[str] = None, name: Optional[str] = None, name_python: Optional[str] = None) -> dict:
    """Get a single dataset by id, name, or name_python.

    Uses profile from .oryxforge configuration to get user_id and project_id.

    Args:
        id: Dataset ID (highest priority)
        name: Dataset name (medium priority)
        name_python: Dataset Python-safe name (lowest priority)

    Returns:
        Dict with id, name, and name_python fields

    Note:
        Parameter priority: id > name > name_python
    """
    project_service = ProjectService()
    return project_service.ds_get(id=id, name=name, name_python=name_python)


@tool
def project_list_sheets(dataset_id: Optional[str] = None, dataset_name: Optional[str] = None, dataset_name_python: Optional[str] = None) -> list[dict]:
    """List all datasheets in the current project or specific dataset.

    Uses profile from .oryxforge configuration to get user_id and project_id.

    Args:
        dataset_id: Dataset ID (if None, list all datasheets in project)
        dataset_name: Dataset name to filter by (lower priority than dataset_id)
        dataset_name_python: Dataset name_python to filter by (lowest priority)

    Returns:
        List of dicts, each containing id, name, name_python, and dataset_id fields for a datasheet

    Note:
        Parameter priority: dataset_id > dataset_name > dataset_name_python
    """
    project_service = ProjectService()
    return project_service.sheet_list(dataset_id, dataset_name, dataset_name_python)


@tool
def project_get_sheet(dataset_id: Optional[str] = None, id: Optional[str] = None, name: Optional[str] = None, name_python: Optional[str] = None) -> dict:
    """Get a single datasheet by id, name, or name_python.

    Uses profile from .oryxforge configuration to get user_id and project_id.

    Args:
        dataset_id: Dataset ID to filter by (optional, searches all project datasets if None)
        id: Datasheet ID (highest priority)
        name: Datasheet name (medium priority)
        name_python: Datasheet Python-safe name (lowest priority)

    Returns:
        Dict with id, name, name_python, and dataset_id fields

    Note:
        Parameter priority: id > name > name_python
    """
    project_service = ProjectService()
    return project_service.sheet_get(dataset_id=dataset_id, id=id, name=name, name_python=name_python)


# DataFrame analysis functions
@tool
def df_describe(file_path: str, head_rows: int = 5, tail_rows: int = 5) -> str:
    """Generate a comprehensive analysis report for a pandas DataFrame from a file.

    Args:
        file_path: Path to the file containing the DataFrame (CSV, parquet, pickle, etc.)
        head_rows: Number of rows to show in head preview (default: 5)
        tail_rows: Number of rows to show in tail preview (default: 5)

    Returns:
        A markdown-formatted string containing the DataFrame analysis report including:
        - Shape and memory usage
        - Column information (names, types, null counts)
        - Head and tail previews
        - Statistical summary
        - Missing values analysis with percentages

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the file format is not supported
    """
    # Detect file format and load DataFrame
    file_path_obj = Path(file_path)

    if not file_path_obj.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    suffix = file_path_obj.suffix.lower()

    if suffix == '.csv':
        df = pd.read_csv(file_path)
    elif suffix == '.parquet':
        df = pd.read_parquet(file_path)
    elif suffix in ['.pkl', '.pickle']:
        df = pd.read_pickle(file_path)
    elif suffix in ['.xlsx', '.xls']:
        df = pd.read_excel(file_path)
    elif suffix == '.json':
        df = pd.read_json(file_path)
    else:
        raise ValueError(f"Unsupported file format: {suffix}")

    return df_svc.describe_pd(df, head_rows=head_rows, tail_rows=tail_rows)


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
    project_get_dataset,
    project_list_sheets,
    project_get_sheet,
    df_describe,
]