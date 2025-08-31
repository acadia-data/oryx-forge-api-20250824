# FastAPI App Tests

This directory contains comprehensive tests for the FastAPI application using pytest and TestClient.

## Test Structure

The tests are organized into logical classes:

- **TestRootEndpoints**: Tests for basic endpoints (/, /hello/{name}, /env)
- **TestLLMEndpoints**: Tests for LLM-related endpoints (/utest-llm, /llm, /llm-openai)
- **TestFilePreviewEndpoint**: Tests for file preview functionality (/files/preview)
- **TestErrorHandling**: Tests for error scenarios and validation

## Setup

1. Install test dependencies:
```bash
pip install -r requirements-test.txt
```

2. Ensure the main app dependencies are installed:
```bash
pip install -r ../requirements.txt
```

## Running Tests

### Option 1: Using the test runner script
```bash
cd api/tests
python run_tests.py
```

### Option 2: Using pytest directly
```bash
cd api/tests
pytest test_files.py -v
```

### Option 3: Run specific test classes
```bash
# Run only root endpoint tests
pytest test_files.py::TestRootEndpoints -v

# Run only file preview tests
pytest test_files.py::TestFilePreviewEndpoint -v
```

### Option 4: Run specific test methods
```bash
# Run a specific test
pytest test_files.py::TestRootEndpoints::test_read_root -v
```

## Test Features

- **Mocking**: Uses unittest.mock to mock external dependencies (Supabase, OpenAI)
- **File Handling**: Creates temporary test files for Excel and Parquet testing
- **Error Scenarios**: Tests various error conditions and edge cases
- **Validation**: Tests request validation and error handling

## Notes

- Tests use mocking to avoid external API calls
- File operations use temporary files that are automatically cleaned up
- The TestClient simulates HTTP requests without starting a server
- All tests are designed to be fast and isolated

## Troubleshooting

If you encounter import errors, ensure you're running from the correct directory and that the app module is accessible in your Python path.
