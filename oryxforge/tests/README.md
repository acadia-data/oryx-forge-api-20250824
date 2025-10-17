# OryxForge Test Suite

This directory contains the test suite for OryxForge, organized as integration and unit tests for various services.

## Table of Contents

- [Quick Start](#quick-start)
- [Test Organization](#test-organization)
- [Running Tests](#running-tests)
- [Test Configuration](#test-configuration)
- [Writing Tests](#writing-tests)
- [CI/CD Integration](#cicd-integration)

## Quick Start

### Run all tests

**On Windows:**
```batch
# Using the batch script
run_tests.bat all

# Or pytest directly
pytest oryxforge/tests/
```

**On Linux/Mac:**
```bash
# Using make (recommended)
make test

# Or pytest directly
pytest oryxforge/tests/
```

### Run specific test file

**On Windows:**
```batch
# Using the batch script
run_tests.bat io

# Or pytest directly
pytest oryxforge/tests/test_io_service.py -v
```

**On Linux/Mac:**
```bash
# Using make
make test-io

# Or pytest directly
pytest oryxforge/tests/test_io_service.py -v
```

### Run with coverage

**On Windows:**
```batch
run_tests.bat cov-html
# Opens htmlcov/index.html
```

**On Linux/Mac:**
```bash
make test-cov-html
# Opens htmlcov/index.html
```

## Test Organization

### Test Files

| File | Description | Type |
|------|-------------|------|
| `test_io_service.py` | IOService tests - save/load DataFrames, charts, markdown | Integration |
| `test_chat_service.py` | ChatService tests - intent classification, chat workflow | Integration |
| `test_project_service.py` | ProjectService tests - dataset/sheet management | Integration |
| `test_workflow_service.py` | Workflow orchestration tests | Integration |
| `test_repo_service.py` | Repository management tests | Integration |
| `test_cli_service.py` | CLI service tests | Integration |
| `test_iam.py` | Identity and access management tests | Unit |
| `test_import_service.py` | Import service tests | Integration |
| `test_mcp.py` | MCP (Model Context Protocol) tests | Integration |
| `test_claude_agent.py` | Claude agent integration tests | Integration |
| `test_config.py` | Shared test configuration and constants | Config |

### Configuration Files

- **`conftest.py`** - Shared pytest fixtures and configuration
- **`test_config.py`** - Test constants (user IDs, project IDs)
- **`data/`** - Test data files

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest oryxforge/tests/

# Run all tests with verbose output
pytest oryxforge/tests/ -v

# Run all tests with extra verbose output
pytest oryxforge/tests/ -vv -s

# Run specific test file
pytest oryxforge/tests/test_io_service.py

# Run specific test class
pytest oryxforge/tests/test_io_service.py::TestIOService

# Run specific test method
pytest oryxforge/tests/test_io_service.py::TestIOService::test_save_and_load_roundtrip
```

### Using Make Commands (Linux/Mac)

The `Makefile` in the project root provides convenient shortcuts:

```bash
# View all available commands
make help

# Run all tests
make test

# Run tests by category
make test-unit           # Unit tests only
make test-integration    # Integration tests only
make test-slow          # Slow tests

# Run service-specific tests
make test-io            # IO service tests
make test-chat          # Chat service tests
make test-project       # Project service tests
make test-workflow      # Workflow tests
make test-repo          # Repository tests
make test-cli           # CLI tests
make test-iam           # IAM tests
make test-import        # Import service tests
make test-mcp           # MCP tests
make test-agent         # Claude agent tests

# Coverage reports
make test-cov           # Terminal coverage report
make test-cov-html      # HTML coverage report

# Utilities
make test-verbose       # Verbose output
make clean-test         # Clean test artifacts
```

### Using Batch Script (Windows)

The `run_tests.bat` script provides the same functionality on Windows:

```batch
# View all available commands
run_tests.bat help

# Run all tests
run_tests.bat all

# Run tests by category
run_tests.bat unit           # Unit tests only
run_tests.bat integration    # Integration tests only
run_tests.bat slow          # Slow tests

# Run service-specific tests
run_tests.bat io            # IO service tests
run_tests.bat chat          # Chat service tests
run_tests.bat project       # Project service tests
run_tests.bat workflow      # Workflow tests
run_tests.bat repo          # Repository tests
run_tests.bat cli           # CLI tests
run_tests.bat iam           # IAM tests
run_tests.bat import        # Import service tests
run_tests.bat mcp           # MCP tests
run_tests.bat agent         # Claude agent tests

# Coverage reports
run_tests.bat cov           # Terminal coverage report
run_tests.bat cov-html      # HTML coverage report

# Utilities
run_tests.bat verbose       # Verbose output
run_tests.bat clean         # Clean test artifacts
```

### Filtering by Markers

Tests are automatically marked based on their characteristics:

```bash
# Run only integration tests
pytest oryxforge/tests/ -m integration

# Run only unit tests
pytest oryxforge/tests/ -m unit

# Run only slow tests
pytest oryxforge/tests/ -m slow

# Skip slow tests
pytest oryxforge/tests/ -m "not slow"

# Run tests that require database data
pytest oryxforge/tests/ -m requires_data
```

### Coverage Reports

```bash
# Generate terminal coverage report
pytest oryxforge/tests/ --cov=oryxforge --cov-report=term-missing

# Generate HTML coverage report
pytest oryxforge/tests/ --cov=oryxforge --cov-report=html
# Open htmlcov/index.html in browser

# Using make
make test-cov          # Terminal report
make test-cov-html     # HTML report
```

## Test Configuration

### Environment Setup

Tests use configuration from `test_config.py`:

```python
# Test user and project IDs for integration tests
TEST_USER_ID = '24d811e2-1801-4208-8030-a86abbda59b8'
TEST_PROJECT_ID = 'fd0b6b50-ed50-49db-a3ce-6c7295fb85a2'
```

### Shared Fixtures

The `conftest.py` provides shared fixtures:

- **`temp_working_dir`** - Temporary directory for test isolation
- **`test_user_id`** - Test user ID from configuration
- **`test_project_id`** - Test project ID from configuration
- **`supabase_client`** - Shared Supabase client (session-scoped)
- **`setup_credentials`** - Configure credentials in temp directory
- **`project_context`** - Set up and tear down ProjectContext

### Pytest Configuration

Configuration in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["oryxforge/tests"]
markers = [
    "asyncio: mark test as async",
    "integration: mark test as an integration test",
    "unit: mark test as a unit test",
    "slow: mark test as slow running",
    "requires_data: mark test as requiring test data in database"
]
```

## Writing Tests

### Using Shared Fixtures

```python
import pytest

class TestMyService:
    def test_with_temp_dir(self, temp_working_dir):
        """Use temporary directory fixture."""
        # temp_working_dir is automatically created and cleaned up
        assert Path(temp_working_dir).exists()

    def test_with_context(self, project_context):
        """Use project context fixture."""
        # ProjectContext is set up and torn down automatically
        from oryxforge.services.io_service import IOService
        io_service = IOService()
        # ... test code ...
```

### Adding Test Markers

```python
import pytest

class TestMyService:
    @pytest.mark.integration
    def test_integration_feature(self):
        """Test that requires external services."""
        pass

    @pytest.mark.slow
    def test_slow_operation(self):
        """Test that takes significant time."""
        pass

    @pytest.mark.unit
    def test_pure_logic(self):
        """Fast unit test with no external dependencies."""
        pass
```

### Test Cleanup

Tests should clean up after themselves:

```python
class TestMyService:
    # Track created resources
    created_files = []

    @pytest.fixture(autouse=True)
    def cleanup(self):
        """Auto-cleanup after each test."""
        yield
        # Cleanup code runs after test
        for file_path in self.created_files:
            Path(file_path).unlink(missing_ok=True)
        self.created_files.clear()

    def test_creates_file(self, temp_working_dir):
        file_path = Path(temp_working_dir) / "test.txt"
        file_path.write_text("test")
        self.created_files.append(file_path)
        # File will be cleaned up automatically
```

### Best Practices

1. **Use fixtures** - Leverage shared fixtures from `conftest.py`
2. **Isolate tests** - Each test should be independent
3. **Clean up resources** - Always clean up created files/records
4. **Use markers** - Mark tests appropriately (integration, slow, etc.)
5. **Clear naming** - Test names should describe what they test
6. **Test one thing** - Each test should verify one behavior
7. **Avoid hardcoding** - Use configuration from `test_config.py`

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run tests
        run: |
          make test-cov

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### Local Pre-commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

echo "Running tests..."
make test-unit
if [ $? -ne 0 ]; then
    echo "Tests failed. Commit aborted."
    exit 1
fi
```

## Known Issues

### Current Test Status

As of the last run (207 tests total):
- ✅ **138 passed** (66.7%)
- ❌ **23 failed** (11.1%)
- ⚠️ **47 errors** (22.7%)
- ⏭️ **1 skipped** (0.5%)

### Known Failing Tests

#### 1. Project Service Tests (21 errors)
**Issue:** `ValueError: Failed to mount data directory at ./data. Please check that rclone is installed`

**Cause:** Tests require `rclone` to be installed and configured for GCS data mounting.

**Workaround:**
```bash
# Skip project service tests
pytest oryxforge/tests/ --ignore=oryxforge/tests/test_project_service.py
```

**Fix:** Install and configure rclone:
```bash
# Install rclone
# Windows: Download from https://rclone.org/downloads/
# Linux: sudo apt-get install rclone
# Mac: brew install rclone

# Configure rclone for GCS
rclone config
```

#### 2. Repo Service Tests (2 errors - Windows only)
**Issue:** `PermissionError: [WinError 32] The process cannot access the file`

**Cause:** Windows file locking prevents cleanup of git repositories in temp directories.

**Workaround:**
```batch
# Skip repo service tests on Windows
pytest oryxforge/tests/ --ignore=oryxforge/tests/test_repo_service.py
```

**Note:** These tests work fine on Linux/Mac.

#### 3. IO Service Tests (34 errors)
**Issue:** Various fixture and setup issues

**Status:** Being investigated. Most IO service functionality works in production.

**Workaround:**
```bash
# Skip IO service tests
pytest oryxforge/tests/ --ignore=oryxforge/tests/test_io_service.py
```

#### 4. Chat Service Tests (8 errors)
**Issue:** `setup_test_environment` fixture conflicts

**Status:** Fixture scoping issue being resolved.

**Workaround:**
```bash
# Skip chat service tests
pytest oryxforge/tests/ --ignore=oryxforge/tests/test_chat_service.py
```

### Running Only Passing Tests

To run only the tests that currently pass:

```bash
# Exclude problematic test files
pytest oryxforge/tests/ \
  --ignore=oryxforge/tests/test_project_service.py \
  --ignore=oryxforge/tests/test_repo_service.py \
  --ignore=oryxforge/tests/test_io_service.py \
  --ignore=oryxforge/tests/test_chat_service.py
```

**On Windows:**
```batch
pytest oryxforge/tests/ --ignore=oryxforge/tests/test_project_service.py --ignore=oryxforge/tests/test_repo_service.py --ignore=oryxforge/tests/test_io_service.py --ignore=oryxforge/tests/test_chat_service.py
```

This will run approximately 138 passing tests, primarily:
- ✅ Claude agent tests
- ✅ CLI service tests
- ✅ IAM tests
- ✅ Import service tests
- ✅ MCP tests
- ✅ Workflow service tests

## Troubleshooting

### Common Issues

**ImportError: No module named 'oryxforge'**
```bash
# Install package in development mode
pip install -e .
```

**Supabase connection errors**
```bash
# Check credentials are configured
oryxforge config show

# Verify test constants in test_config.py are valid
```

**Tests fail due to missing test data**
```bash
# Some tests require data in the test project
# Check test output for specific requirements
# Or skip tests with: pytest -m "not requires_data"
```

**Permission errors on Windows**
```bash
# Run as administrator or check file permissions
# Ensure temp directories are writable
# Known issue with repo service tests - use workaround above
```

## Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [OryxForge Documentation](https://docs.oryxforge.dev)

## Questions?

For questions or issues:
- Check the [OryxForge GitHub Issues](https://github.com/oryxforge/oryxforge/issues)
- Contact: dev@oryxintel.com
