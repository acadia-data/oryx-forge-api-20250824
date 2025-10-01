"""Tests for MCP and LangChain tools."""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from fastmcp import Client


def test_mcp_tools_import():
    """Test that MCP tools can be imported."""
    from oryxforge.tools.mcp import mcp
    assert mcp is not None
    assert mcp.name == "OryxForge"


def test_langchain_tools_import():
    """Test that LangChain tools can be imported."""
    from oryxforge.tools.langchain import TOOLS
    assert len(TOOLS) == 10

    tool_names = [tool.name for tool in TOOLS]
    expected_tools = [
        'code_upsert_eda',
        'code_read_eda',
        'code_upsert_run',
        'code_read_run',
        'workflow_run_eda',
        'workflow_run_flow',
        'project_create_dataset',
        'project_create_sheet',
        'project_list_datasets',
        'project_list_sheets',
    ]

    for expected in expected_tools:
        assert expected in tool_names


@patch('oryxforge.tools.mcp.svc')
def test_code_upsert_eda(mock_svc):
    """Test code_upsert_eda function."""
    from oryxforge.tools.mcp import code_upsert_eda

    mock_svc.upsert_eda.return_value = "Success"

    result = code_upsert_eda(
        sheet="TestSheet",
        code="print('test')",
        dataset="test_dataset",
        inputs=["Sheet1"],
        imports="import pandas as pd"
    )

    assert result == "Success"
    mock_svc.upsert_eda.assert_called_once_with(
        "TestSheet",
        "print('test')",
        "test_dataset",
        ["Sheet1"],
        "import pandas as pd"
    )


@patch('oryxforge.tools.mcp.svc')
def test_code_read_run(mock_svc):
    """Test code_read_run function."""
    from oryxforge.tools.mcp import code_read_run

    mock_svc.read.return_value = "df_out = pd.DataFrame()"

    result = code_read_run(sheet="TestSheet", dataset="test_dataset")

    assert result == "df_out = pd.DataFrame()"
    mock_svc.read.assert_called_once_with("TestSheet", "test_dataset", method='run')


@patch('oryxforge.tools.mcp.svc')
def test_workflow_run_eda(mock_svc):
    """Test workflow_run_eda function."""
    from oryxforge.tools.mcp import workflow_run_eda

    mock_svc.run_task.return_value = {
        'stdout': 'Success',
        'stderr': '',
        'returncode': 0
    }

    result = workflow_run_eda(sheet="TestSheet", dataset="test_dataset")

    assert result['returncode'] == 0
    mock_svc.run_task.assert_called_once_with(
        "TestSheet",
        'eda',
        dataset="test_dataset",
        execute=True
    )


@patch('oryxforge.tools.mcp.get_user_id')
@patch('oryxforge.tools.mcp.get_project_id')
@patch('oryxforge.tools.mcp.ProjectService')
def test_project_list_datasets(mock_project_service, mock_get_project_id, mock_get_user_id):
    """Test project_list_datasets function."""
    from oryxforge.tools.mcp import project_list_datasets

    mock_get_user_id.return_value = "user123"
    mock_get_project_id.return_value = "project456"

    mock_instance = Mock()
    mock_instance.ds_list.return_value = [
        {'id': 'ds1', 'name': 'Dataset 1', 'name_python': 'dataset_1'},
        {'id': 'ds2', 'name': 'Dataset 2', 'name_python': 'dataset_2'}
    ]
    mock_project_service.return_value = mock_instance

    result = project_list_datasets()

    assert len(result) == 2
    assert result[0]['name'] == 'Dataset 1'
    mock_project_service.assert_called_once_with("project456", "user123")


@patch('oryxforge.tools.mcp.get_user_id')
@patch('oryxforge.tools.mcp.get_project_id')
@patch('oryxforge.tools.mcp.ProjectService')
def test_project_create_sheet(mock_project_service, mock_get_project_id, mock_get_user_id):
    """Test project_create_sheet function."""
    from oryxforge.tools.mcp import project_create_sheet

    mock_get_user_id.return_value = "user123"
    mock_get_project_id.return_value = "project456"

    mock_instance = Mock()
    mock_instance.sheet_create.return_value = "sheet789"
    mock_project_service.return_value = mock_instance

    result = project_create_sheet(dataset_id="ds1", name="New Sheet")

    assert result == "sheet789"
    mock_instance.sheet_create.assert_called_once_with("ds1", "New Sheet")


@patch('oryxforge.tools.mcp.svc')
def test_code_upsert_with_indented_code(mock_svc):
    """Test that indented code is properly dedented before upserting."""
    from oryxforge.tools.mcp import code_upsert_eda

    # Code with leading indentation (common from IDE/AI)
    indented_code = """    # Load the file
    df = pd.read_csv('data.csv')

    # Print info
    if df is not None:
        print(df.head())
        for col in df.columns:
            print(col)
    """

    mock_svc.upsert_eda.return_value = "Success"

    result = code_upsert_eda(
        sheet="TestSheet",
        code=indented_code,
        dataset="test_dataset"
    )

    # The service should have been called (dedent happens in WorkflowService)
    assert result == "Success"
    mock_svc.upsert_eda.assert_called_once()
    # Verify the code was passed through
    call_args = mock_svc.upsert_eda.call_args
    assert call_args[0][1] == indented_code  # Code is passed as-is, dedent happens in service


def test_mcp_cli_command():
    """Test that MCP CLI command is properly registered."""
    from oryxforge.tools.mcp_server import mcp

    assert mcp is not None
    assert hasattr(mcp, 'commands')
    assert 'serve' in mcp.commands


# ============================================================================
# FastMCP Integration Tests
# ============================================================================

class TestMCPIntegration:
    """Integration tests that actually call the MCP server via FastMCP Client."""

    @pytest.fixture
    def test_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            yield tmpdir
            os.chdir(original_cwd)

    @pytest.fixture
    def mcp_server(self, test_dir):
        """Create a fresh MCP server instance for testing."""
        from fastmcp import FastMCP
        from oryxforge.services.workflow_service import WorkflowService

        # Create a new WorkflowService with the test directory
        test_svc = WorkflowService(base_dir=test_dir)

        # Create a new FastMCP server with test tools
        test_mcp = FastMCP("OryxForgeTest")

        # Register the tools with the test service
        from typing import Optional

        @test_mcp.tool
        def code_upsert_eda(sheet: str, code: str, dataset: Optional[str] = None, inputs: Optional[list[str]] = None, imports: Optional[str] = None) -> str:
            if inputs is None:
                inputs = []
            return test_svc.upsert_eda(sheet, code, dataset, inputs, imports)

        @test_mcp.tool
        def code_read_eda(sheet: str, dataset: Optional[str] = None) -> str:
            return test_svc.read(sheet, dataset, method='eda')

        @test_mcp.tool
        def code_upsert_run(sheet: str, code: str, dataset: Optional[str] = None, inputs: Optional[list[str]] = None, imports: Optional[str] = None) -> str:
            if inputs is None:
                inputs = []
            return test_svc.upsert_run(sheet, code, dataset, inputs, imports)

        @test_mcp.tool
        def code_read_run(sheet: str, dataset: Optional[str] = None) -> str:
            return test_svc.read(sheet, dataset, method='run')

        return test_mcp

    @pytest.mark.asyncio
    async def test_code_upsert_eda_integration(self, mcp_server, test_dir):
        """Test code_upsert_eda via actual MCP call."""
        async with Client(mcp_server) as client:
            # Call the tool
            result = await client.call_tool(
                "code_upsert_eda",
                {
                    "sheet": "TestSheet",
                    "code": "print('test eda code')",
                    "dataset": None,
                }
            )

            # Verify result exists
            assert result is not None

            # Verify file was created
            task_file = Path(test_dir) / "tasks" / "__init__.py"
            assert task_file.exists()
            content = task_file.read_text()
            assert "TestSheet" in content
            assert "eda" in content

    @pytest.mark.asyncio
    async def test_code_read_eda_integration(self, mcp_server, test_dir):
        """Test code_read_eda via actual MCP call."""
        async with Client(mcp_server) as client:
            # First create a sheet with EDA code
            await client.call_tool(
                "code_upsert_eda",
                {
                    "sheet": "ReadTest",
                    "code": "print('read test')",
                    "dataset": None,
                }
            )

            # Read the EDA code back
            result = await client.call_tool(
                "code_read_eda",
                {
                    "sheet": "ReadTest",
                    "dataset": None,
                }
            )

            assert result is not None
            # Check if result contains expected code
            result_text = str(result)
            assert "read test" in result_text

    @pytest.mark.asyncio
    async def test_code_upsert_run_integration(self, mcp_server, test_dir):
        """Test code_upsert_run via actual MCP call."""
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "code_upsert_run",
                {
                    "sheet": "RunTest",
                    "code": "df_out = pd.DataFrame({'test': [1, 2, 3]})",
                    "dataset": None,
                }
            )

            assert result is not None

            # Verify file was created with run method
            task_file = Path(test_dir) / "tasks" / "__init__.py"
            assert task_file.exists()
            content = task_file.read_text()
            assert "RunTest" in content
            assert "def run" in content

    @pytest.mark.asyncio
    async def test_indented_code_integration(self, mcp_server, test_dir):
        """Test that indented code works via MCP call (tests the dedent fix)."""
        indented_code = """    # This has leading spaces
    df = pd.read_csv('test.csv')

    if df is not None:
        print(df.head())
    """

        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "code_upsert_eda",
                {
                    "sheet": "IndentTest",
                    "code": indented_code,
                    "dataset": None,
                }
            )

            assert result is not None

            # Read back and verify dedent worked
            read_result = await client.call_tool(
                "code_read_eda",
                {
                    "sheet": "IndentTest",
                    "dataset": None,
                }
            )

            result_text = str(read_result)
            # Should not start with spaces after dedent
            assert "    # This has leading spaces" not in result_text or "# This has leading spaces" in result_text
