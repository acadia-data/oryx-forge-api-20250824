# OryxForge MCP Server

MCP (Model Context Protocol) server for OryxForge - providing tools and resources for code generation and data processing.

## Features

### File Operations
- Read and preview data files (CSV, Excel, Parquet)
- List available data files
- Upload new data files
- Get detailed file information

### Code Generation
- Create data processing tasks
- Update existing tasks
- List tasks in workflows
- Delete tasks
- Generate complete workflow code
- Read task code
- Rename tasks and update dependencies

### Data Processing
- Analyze data files with comprehensive insights
- Suggest data transformations
- Detect data quality issues
- Generate data summary reports

## Installation

```bash
cd mcp-server
pip install -e .
```

## Usage

Run the MCP server:

```bash
python -m mcp-server.main
```

The server will start and listen for MCP protocol messages via stdio.

## Configuration

- **Data Directory**: Set via `data_directory` parameter (default: "data")
- **Output Directory**: Set via `output_directory` parameter (default: "generated_workflows")

## Dependencies

- `mcp`: Model Context Protocol implementation
- `pandas`: Data manipulation
- `numpy`: Numerical operations
- `openpyxl`: Excel file support
- `pyarrow`: Parquet file support
