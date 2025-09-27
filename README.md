# OryxForge

Task management and workflow orchestration library with MCP support.

## Features

- **WorkflowService**: Dynamic task creation and management using AST manipulation
- **MCP Integration**: Model Context Protocol tools for remote task management
- **CLI Interface**: Command-line tools for task orchestration
- **d6tflow Compatible**: Generated tasks work seamlessly with d6tflow

## Installation

### Basic Installation
```bash
pip install oryxforge
```

### With CLI Support
```bash
pip install oryxforge[cli]
```

### With MCP Server Support
```bash
pip install oryxforge[mcp-server]
```

### Development Installation
```bash
pip install oryxforge[dev]
```

## Quick Start

### Using WorkflowService Directly

```python
from oryxforge import WorkflowService

# Create service
svc = WorkflowService()

# Create a task
svc.create(
    module="data_pipeline",
    task="ExtractData", 
    code="""
df = pd.read_csv('input.csv')
self.output().write(df)
""",
    dependencies=[]
)

# List tasks
print(svc.list_tasks("data_pipeline"))
```

### Using MCP Server

```bash
# Start MCP server
oryxforge mcp serve

# In another terminal, use MCP client to connect
# Server will be available on stdio transport
```

### CLI Usage

```bash
# List available commands
oryxforge --help

# List MCP tools
oryxforge mcp list-tools

# Start MCP server
oryxforge mcp serve
```

## Documentation

- [MCP CLI Guide](docs/mcp-cli.md) - Complete guide to MCP tools and CLI usage

## Requirements

- Python 3.8+
- d6tflow>=1.0.0
- pandas>=1.3.0

### Optional Dependencies

- click>=8.0.0 (for CLI)
- mcp>=0.1.0 (for MCP server)

## License

MIT License