# CLAUDE.md - OryxForge API Development Guide

This document provides guidance for AI agents (including Claude) working on the OryxForge API codebase.

## Workflow

### Plan, Design, Think Before Implementing

1. **Understand the Context**: Before making changes, understand how services interact:
   - Services use `ProjectContext` (from `env_config.py`) for configuration
   - No parameters for user_id/project_id - these come from context
   - All services depend on Supabase for data persistence
   - d6tflow tasks handle workflow orchestration
   - CLI commands orchestrate service calls

2. **Service Integration Planning**: Consider how different services fit together:
   - `ProjectService` - Core project/dataset/sheet operations, d6tflow integration
   - `IOService` - File I/O (DataFrames as Parquet, Plotly charts, Markdown)
   - `ChatService` - Claude Agent SDK integration with session management
   - `CLIService` - User-facing operations, profile management, mode switching
   - `RepoService` - Git/GitLab repository management
   - `WorkflowService` - d6tflow task orchestration
   - `ConfigService` - .oryxforge.cfg file management
   - `CredentialsManager` - Authentication and profile storage
   - `ImportService` - File import orchestration

3. **Design Decisions**:
   - Use zero-parameter service pattern (context-based configuration)
   - Follow existing patterns for Supabase queries (RLS-aware)
   - Respect ProjectContext for working directory and credentials
   - Use d6tflow for workflow tasks, not ad-hoc scripts
   - Platform-agnostic code (Windows + Linux support)
   - **Serverless-first design**: The API runs on serverless infrastructure (GCP Cloud Run/Functions) that resets frequently - all state must be stored in Supabase or GCS, and the environment must be quickly recreatable from scratch

### Create and Run Tests for New Meaningful Functionality

- Write integration tests for new service methods
- Use existing fixtures from `conftest.py`
- Run tests before committing: `make test` or `pytest oryxforge/tests/`
- Ensure tests pass on both platforms

## Code Style

### Keep Code Efficient and DRY

**Zero-Parameter Services Pattern:**
```python
# GOOD - Uses ProjectContext
def create_dataset(name: str) -> Dict[str, Any]:
    context = ProjectContext.get()
    supabase = init_supabase_client()
    result = supabase.table("datasets").insert({
        "name": name,
        "project_id": context.project_id,
        "user_owner": context.user_id
    }).execute()
    return result.data[0]

# BAD - Parameters for context values
def create_dataset(name: str, user_id: str, project_id: str) -> Dict[str, Any]:
    # Don't do this!
    pass
```

**Supabase Query Pattern:**
```python
# Filter by user_owner and project_id for RLS compliance
supabase = init_supabase_client()
result = supabase.table("datasets") \
    .select("*") \
    .eq("project_id", context.project_id) \
    .eq("user_owner", context.user_id) \
    .execute()
```

**Platform-Agnostic Code:**
```python
from pathlib import Path
import sys

# Use pathlib for cross-platform paths
path = Path(context.working_dir) / "data" / "file.parquet"

# Handle Windows encoding if needed
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
```

**Error Handling:**
```python
# Raise meaningful errors
if not dataset_id:
    raise ValueError("Dataset ID is required")

# Catch specific exceptions
try:
    result = supabase.table("datasets").select("*").eq("id", dataset_id).execute()
    if not result.data:
        raise ValueError(f"Dataset not found: {dataset_id}")
except Exception as e:
    logger.error(f"Failed to fetch dataset: {e}")
    raise
```

### Include Docstrings

All functions must have Google-style docstrings with type hints:

```python
def save_dataframe(df: pd.DataFrame, name_python: str, dataset_id: str) -> str:
    """Save a DataFrame to Parquet format and register in Supabase.

    Uses ProjectContext to determine working directory and credentials.
    Saves file to {working_dir}/data/{dataset_id}/{name_python}.parquet
    and creates a datasheet record in Supabase.

    Args:
        df: DataFrame to save
        name_python: Python-compatible name (PascalCase for sheets)
        dataset_id: UUID of parent dataset

    Returns:
        UUID of created datasheet record

    Raises:
        ValueError: If dataset_id is invalid or df is empty
        FileNotFoundError: If working directory doesn't exist

    Example:
        >>> df = pd.DataFrame({"col1": [1, 2, 3]})
        >>> sheet_id = save_dataframe(df, "MySheet", dataset_id)
    """
    context = ProjectContext.get()
    # ... implementation
```

**Key Docstring Requirements:**
- One-line summary describing what the function does
- Detailed description explaining behavior, context usage, side effects
- Args section with type and description for each parameter
- Returns section describing return value and type
- Raises section for expected exceptions
- Example usage when helpful for understanding

## Deployment Architecture

### Serverless Infrastructure

The OryxForge API is deployed on **serverless infrastructure** (GCP Cloud Run/Cloud Functions) which has the following characteristics:

**Environment Resets:**
- Containers/functions spin up and down frequently based on demand
- Local file system is ephemeral and resets between invocations
- No persistent state can be stored on the server itself
- Working directories (`/tmp/{user_id}/{project_id}`) are temporary

**Design Implications:**

1. **All State in Supabase**: Store all application state (projects, datasets, sheets, chat history) in Supabase
   - Never rely on in-memory caches that survive across requests
   - Query Supabase for fresh data on each request
   - Use RLS (Row-Level Security) for multi-tenant isolation

2. **Files in Cloud Storage**: Store all user files (Parquet, charts, markdown) in Google Cloud Storage
   - Use `gcsfs` for GCS access
   - Mount GCS buckets using rclone (mount/unmount operations)
   - File paths: `gs://bucket/projects/{user_id}/{project_id}/data/{dataset_id}/{sheet}.parquet`

3. **Quick Environment Recreation**: Services must be able to initialize quickly from scratch
   - `ProjectContext.set()` establishes environment from request parameters
   - No reliance on `.oryxforge.cfg` file in deployed API mode
   - Credentials come from environment variables, not local files
   - Working directory created on-demand in `/tmp`

4. **Idempotent Operations**: Design operations to be safely retried
   - Check if resources exist before creating
   - Use database transactions where needed
   - Handle partial failures gracefully

**Mode Detection (from env_config.py):**
```python
# GCP Production (serverless)
if os.getenv("GOOGLE_CLOUD_PROJECT"):
    working_dir = f"/tmp/{user_id}/{project_id}"
    # Ephemeral, resets frequently

# Local API Development
elif os.getenv("ORYX_MOUNT_ROOT"):
    working_dir = f"{ORYX_MOUNT_ROOT}/mnt/projects/{user_id}/{project_id}"
    # Persistent during development

# CLI Mode
else:
    working_dir = os.getcwd()
    # User's local project directory
```

**Best Practices for Serverless:**
- Don't cache data in module-level variables (use request-scoped context)
- Don't write to local files unless they're in `/tmp` and immediately uploaded to GCS
- Don't rely on background processes or cron jobs (use Cloud Scheduler + Pub/Sub)
- Keep cold start time low (minimize imports, lazy load heavy dependencies)
- Handle concurrent requests safely (use database locks if needed)

## Tech Stack Reference

### Core Dependencies
- **Python**: 3.12+
- **Database**: Supabase (PostgreSQL with RLS)
- **Workflow**: d6tflow (task-based pipelines)
- **AI/ML**: claude-agent-sdk, langchain-openai
- **CLI**: Click 8.0+
- **Data**: pandas, pyarrow (Parquet)
- **Cloud**: gcsfs (Google Cloud Storage)
- **Testing**: pytest, pytest-asyncio, pytest-cov
- **Code Quality**: black, ruff, mypy, pre-commit

### Project Structure
```
oryxforge/
├── cli/              # Click command groups (main, admin, agent, dev)
├── services/         # Core service layer (13 services)
├── agents/           # Claude Agent wrapper
├── tools/            # MCP and LangChain integrations
├── tasks/            # d6tflow task implementations
└── tests/            # Integration tests (205 tests, 94% passing)
```

## Tests

### Tests Should Just Test Core Functionality

**Focus on Integration Tests:**
```python
# GOOD - Tests core business logic
def test_create_dataset(test_user_id, test_project_id, temp_working_dir):
    """Test dataset creation and retrieval."""
    context = ProjectContext.set(temp_working_dir, test_user_id, test_project_id)

    # Create dataset
    dataset = create_dataset("Test Dataset")
    assert dataset["name"] == "Test Dataset"
    assert dataset["project_id"] == test_project_id

    # Verify it's in Supabase
    datasets = get_datasets()
    assert any(d["id"] == dataset["id"] for d in datasets)

    ProjectContext.clear()

# BAD - Tests trivial functionality
def test_string_concatenation():
    """Test that strings can be concatenated."""
    result = "hello" + " " + "world"
    assert result == "hello world"
```

### Tests Should Be Integration Tests

- Test service methods that interact with Supabase
- Test CLI commands end-to-end
- Test d6tflow task execution
- Test file I/O operations
- Use real Supabase connection (test project)
- Skip tests if test data unavailable

### Use Common Settings from Fixtures

**Available Fixtures (conftest.py):**

```python
# Use these fixtures instead of hardcoding
@pytest.fixture
def test_user_id() -> str:
    """Session-scoped test user ID."""
    return "24d811e2-1801-4208-8030-a86abbda59b8"

@pytest.fixture
def test_project_id() -> str:
    """Session-scoped test project ID."""
    return "fd0b6b50-ed50-49db-a3ce-6c7295fb85a2"

@pytest.fixture
def temp_working_dir() -> Generator[Path, None, None]:
    """Function-scoped temporary directory."""
    # ... yields temp dir, cleans up after

@pytest.fixture
def supabase_client():
    """Class-scoped Supabase client."""
    # ... yields initialized client

@pytest.fixture
def project_context(test_user_id, test_project_id, temp_working_dir):
    """ProjectContext setup and cleanup."""
    # ... sets context, yields, clears context
```

**Example Test Using Fixtures:**

```python
def test_io_service_save_load(test_user_id, test_project_id, temp_working_dir):
    """Test DataFrame save and load roundtrip."""
    # Setup context
    context = ProjectContext.set(temp_working_dir, test_user_id, test_project_id)

    # Test core functionality
    df = pd.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})
    sheet_id = save_dataframe(df, "TestSheet", dataset_id)

    # Verify
    loaded_df = load_dataframe(sheet_id)
    pd.testing.assert_frame_equal(df, loaded_df)

    # Cleanup
    ProjectContext.clear()
```

### Don't Create Tests for Trivial Functionality

**Skip testing:**
- Simple getters/setters without logic
- Trivial string formatting
- Direct pass-through to library functions
- Type conversions without validation

**Do test:**
- Business logic (e.g., dataset creation, validation)
- Service integration (e.g., Supabase queries)
- File I/O operations (e.g., Parquet save/load)
- CLI commands (e.g., activation, import)
- Error handling and edge cases

## Testing Commands

```bash
# Run all tests
make test

# Run specific service tests
make test-io
make test-chat
make test-project

# Run with coverage
make test-cov-html

# Run specific test file
pytest oryxforge/tests/test_io_service.py -v

# Run specific test
pytest oryxforge/tests/test_io_service.py::test_save_dataframe -v
```

## Configuration & Context

### ProjectContext Usage

```python
from oryxforge.services.env_config import ProjectContext

# Set context (usually done by CLI or API)
context = ProjectContext.set(
    working_dir="/path/to/project",
    user_id="user-uuid",
    project_id="project-uuid"
)

# Get context in service methods
context = ProjectContext.get()
print(f"Working dir: {context.working_dir}")
print(f"User ID: {context.user_id}")
print(f"Project ID: {context.project_id}")

# Clear context (in tests or cleanup)
ProjectContext.clear()
```

### .oryxforge.cfg Format

```ini
[profile]
user_id = 24d811e2-1801-4208-8030-a86abbda59b8
project_id = fd0b6b50-ed50-49db-a3ce-6c7295fb85a2

[mount]
mount_point = D:/data/projects/{user_id}/{project_id}/data
mount_ensure = false  # false in tests, true in CLI

[active]
dataset_id = <uuid>
sheet_id = <uuid>
mode = explore  # explore, edit, plan
```

## Database Schema Reference

### Key Tables

**projects**
- `id` (UUID, PK)
- `name` (text)
- `user_owner` (UUID, RLS)
- `created_at` (timestamp)

**datasets**
- `id` (UUID, PK)
- `name` (text, display name)
- `name_python` (text, snake_case)
- `project_id` (UUID, FK)
- `user_owner` (UUID, RLS)
- `created_at` (timestamp)

**datasheets**
- `id` (UUID, PK)
- `name` (text, display name)
- `name_python` (text, PascalCase)
- `dataset_id` (UUID, FK)
- `type` (text, e.g., "dataframe", "chart", "markdown")
- `uri` (text, file path or legacy URI)
- `metadata` (jsonb)
- `user_owner` (UUID, RLS)
- `created_at` (timestamp)

**chat_messages**
- `id` (UUID, PK)
- `role` (text, "user" or "assistant")
- `content` (text)
- `project_id` (UUID, FK)
- `session_id` (UUID, groups messages)
- `metadata` (jsonb)
- `user_owner` (UUID, RLS)
- `created_at` (timestamp)

**data_sources**
- `id` (UUID, PK)
- `uri` (text)
- `name` (text)
- `type` (text)
- `status` (text)
- `project_id` (UUID, FK)
- `user_owner` (UUID, RLS)
- `created_at` (timestamp)

## Common Patterns

### Logging
```python
from loguru import logger

logger.debug("Debug message")
logger.info("Info message")
logger.success("Success message")
logger.warning("Warning message")
logger.error("Error message")
```

### Type Hints
```python
from typing import Dict, List, Optional, Any
from pathlib import Path
import pandas as pd

def process_data(
    df: pd.DataFrame,
    output_path: Path,
    metadata: Optional[Dict[str, Any]] = None
) -> List[str]:
    """Process data and return list of created files."""
    # ... implementation
```

### Async Operations
```python
import asyncio

async def async_operation() -> str:
    """Async operation example."""
    result = await some_async_call()
    return result

# In tests
@pytest.mark.asyncio
async def test_async_operation():
    """Test async operation."""
    result = await async_operation()
    assert result is not None
```

## Pre-commit Checks

Before committing, ensure:
1. Tests pass: `make test`
2. Code formatted: `black oryxforge/`
3. Linting clean: `ruff check oryxforge/`
4. Type checking: `mypy oryxforge/`
5. All docstrings present and complete

## Questions?

- Check existing service implementations in `oryxforge/services/`
- Review test examples in `oryxforge/tests/`
- See TESTING.md for detailed testing documentation
- Review pyproject.toml for dependency versions and configuration
