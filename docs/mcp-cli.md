# OryxForge MCP CLI Guide

This guide covers how to use the OryxForge Model Context Protocol (MCP) server and tools for task management.

## Installation

Install OryxForge with MCP support:

```bash
pip install oryxforge[mcp-server]
```

This installs:
- `oryxforge` - Core library with TaskService
- `click` - CLI framework
- `mcp-server` - MCP server dependencies

## Starting the MCP Server

Start the MCP server in your project directory:

```bash
cd /path/to/your/project
oryxforge mcp serve
```

Output:
```
Starting OryxForge MCP server with stdio transport...
Working directory: /path/to/your/project
Tasks directory: /path/to/your/project/tasks
Registered tool: create_task
Registered tool: read_task
...
Registered 13 tools
```

The server will:
- Use your current directory as the working directory
- Create a `tasks/` subdirectory for task modules
- Listen on stdio transport for MCP clients

## CLI Commands

### Server Management

```bash
# Start MCP server (stdio transport)
oryxforge mcp serve

# List available MCP tools
oryxforge mcp list-tools

# Show version information  
oryxforge mcp version
```

### List Tools Output Example

```bash
$ oryxforge mcp list-tools
Available MCP tools:
==================================================
• create_task(module: str, task: str, code: str, dependencies: list[str] = None) -> str
  Create a new task class in the specified module.

• read_task(module: str, task: str) -> str
  Read the source code of a task class.

• change_working_directory(path: str) -> str
  Change the working directory for the task service.
  
Total: 13 tools
```

## Claude setup

```bash
claude mcp add oryx -- oryxforge mcp serve
claude mcp remove oryxforge
claude mcp remove mcp_server
claude mcp remove OryxForge

fastmcp run mcp_server.py
fastmcp install claude-code mcp_server
fastmcp install claude-code mcp_oryxforge.py

claude --debug
npx @modelcontextprotocol/inspector oryxforge mcp serve



```



/mcp to check status

## fastmcp cli

```bash
fastmcp run mcp_oryxforge.py
fastmcp install claude-code mcp_oryxforge.py

```

## Available MCP Tools

### Task Management

#### `create_task(module, task, code, dependencies=None)`
Create a new task class.

**Parameters:**
- `module`: Module name (e.g., "data_processing")
- `task`: Task class name (e.g., "LoadData") 
- `code`: Python code for the run() method
- `dependencies`: List of dependency task names (optional)

**Example:**
```python
create_task(
    module="etl", 
    task="ExtractData",
    code="""
df = pd.read_csv('input.csv')
self.output().write(df)
""",
    dependencies=[]
)
```

#### `read_task(module, task)`
Read the source code of a task class (run method body only by default).

**Example:**
```python
read_task("etl", "ExtractData")
# Returns: "df = pd.read_csv('input.csv')\nself.output().write(df)"
```

#### `update_task(module, task, new_code=None, new_dependencies=None)`
Update an existing task class.

**Example:**
```python
update_task(
    module="etl",
    task="ExtractData", 
    new_code="df = pd.read_csv('updated_input.csv')\nself.output().write(df)"
)
```

#### `upsert_task(module, task, code, dependencies=None)`
Create a new task or update if it exists.

#### `delete_task(module, task)`
Delete a task class from a module.

#### `rename_task(module, old_task, new_task)`
Rename a task and update all dependency references.

### Module Management

#### `list_modules()`
List all available task modules.

**Example:**
```python
list_modules()
# Returns: ["etl", "data_processing", "ml_training"]
```

#### `list_tasks(module)`
List all tasks in a specific module.

**Example:**
```python
list_tasks("etl")
# Returns: ["ExtractData", "TransformData", "LoadData"]
```

### Directory Navigation

#### `get_working_directory()`
Get current working directory.

#### `get_tasks_directory()`
Get the tasks directory path.

#### `change_working_directory(path)`
Change working directory and reinitialize TaskService.

**Examples:**
```python
change_working_directory("~/my-project")
change_working_directory("../other-project")  
change_working_directory("/absolute/path")
```

#### `list_directory(path=".")`
List directory contents.

**Example:**
```python
list_directory()  # Current directory
list_directory("../")  # Parent directory
# Returns: ["file1.py", "tasks/", "README.md"]
```

## Usage Workflow

### 1. Start Server in Project Directory

```bash
cd /path/to/your/data-project
oryxforge mcp serve
```

### 2. Connect MCP Client

Use any MCP-compatible client (Claude Desktop, etc.) to connect to the server.

### 3. Create Task Structure

```python
# Create data extraction task
create_task(
    module="pipeline",
    task="ExtractCustomerData", 
    code="""
# Extract customer data from database
df = pd.read_sql('SELECT * FROM customers', connection)
self.output().write(df)
""",
    dependencies=[]
)

# Create transformation task that depends on extraction
create_task(
    module="pipeline",
    task="CleanCustomerData",
    code="""
# Clean and validate customer data  
df = self.input().read()
df = df.dropna()
df['email'] = df['email'].str.lower()
self.output().write(df)
""", 
    dependencies=["ExtractCustomerData"]
)
```

### 4. Manage Tasks

```python
# List all modules
list_modules()

# List tasks in pipeline module
list_tasks("pipeline")

# Read a task's code
read_task("pipeline", "ExtractCustomerData")

# Update task code
update_task(
    module="pipeline",
    task="ExtractCustomerData",
    new_code="""
# Updated extraction with error handling
try:
    df = pd.read_sql('SELECT * FROM customers WHERE active=1', connection)
    self.output().write(df)
except Exception as e:
    print(f"Extraction failed: {e}")
    raise
"""
)
```

### 5. Navigate Projects

```python
# Switch to different project
change_working_directory("~/other-project")

# Verify new location
get_working_directory()
get_tasks_directory()

# List contents 
list_directory()
```

## File Structure

The MCP tools create this structure in your project:

```
your-project/
├── tasks/                    # Task modules directory
│   ├── __init__.py          # Package init
│   ├── pipeline.py          # Task module
│   └── analytics.py         # Another task module
├── data/                    # Your data files
└── config.py               # Your config
```

## Error Handling

All tools provide clear error messages:

```python
# Directory doesn't exist
change_working_directory("/nonexistent")
# Returns: "Error: Directory does not exist: /nonexistent"

# Task not found
read_task("missing_module", "MissingTask") 
# Returns: "Error: Class MissingTask not found in missing_module"

# Permission denied
list_directory("/root")
# Returns: ["Error: Permission denied accessing: /root"]
```

## Integration with d6tflow

Tasks created through MCP are compatible with d6tflow:

```python
import d6tflow
from tasks.pipeline import ExtractCustomerData, CleanCustomerData

# Run tasks
d6tflow.run(CleanCustomerData())

# Check task status
d6tflow.preview(CleanCustomerData())
```

## Best Practices

1. **Organize by domain**: Use descriptive module names like "etl", "ml_training", "reporting"

2. **Clear task names**: Use PascalCase for task names like "ExtractCustomerData" 

3. **Document dependencies**: Always specify task dependencies for proper execution order

4. **Handle errors**: Include error handling in task code for robustness

5. **Version control**: Commit the generated `tasks/` directory to track your workflow

6. **Working directory**: Start the server in your project root for consistent paths

## Troubleshooting

### Server won't start
- Check that `oryxforge[mcp-server]` is installed
- Ensure you have write permissions in the current directory

### Tasks not found
- Verify you're in the correct working directory with `get_working_directory()`
- Check module exists with `list_modules()`
- Use `list_directory()` to see current directory contents

### Permission errors
- Ensure the server has read/write access to the tasks directory
- Check file permissions if running on shared systems

### Import errors in generated tasks
- Verify d6tflow and pandas are installed in your environment
- Check that task dependencies are properly specified