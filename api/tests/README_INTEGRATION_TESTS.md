# FileService Integration Tests

This directory contains comprehensive integration tests for the FileService class that test real database and storage operations.

## Overview

The integration tests are designed to:
- Test real Supabase database operations
- Test actual file upload/download from storage
- Use authenticated user context
- Validate end-to-end workflows
- Use dynamic data validation instead of hardcoded assertions

## Test Structure

### Files

- `conftest.py` - Pytest fixtures for test configuration and setup
- `test_file_service_integration.py` - Main integration test class
- `test-cfg.yaml` - Test configuration with user credentials
- `pytest.ini` - Pytest configuration
- `requirements-test.txt` - Test dependencies
- `run_integration_tests.py` - Test runner script

### Test Categories

1. **FileService Initialization and Data Retrieval**
   - Tests service initialization with real Supabase client
   - Tests data source record retrieval
   - Tests error handling for non-existent records

2. **File Download and Preview Workflow**
   - Tests file download from Supabase storage
   - Tests file preview for CSV and Parquet formats
   - Tests file cleanup operations

3. **Excel File Processing**
   - Tests Excel files with multiple sheets
   - Tests dynamic validation of sheet data
   - Tests file import functionality

4. **Error Handling**
   - Tests unsupported file types
   - Tests cleanup of non-existent files
   - Tests various error scenarios

5. **Database Record Management**
   - Tests dataset record creation
   - Tests datasheet record creation
   - Tests data source status updates

6. **Complete Workflow Testing**
   - Tests end-to-end file processing for all formats
   - Tests dynamic validation based on test data
   - Tests import functionality with real data

## Key Features

### Dynamic Data Validation

Instead of hardcoded assertions, the tests use the test data itself as the source of truth:

```python
# Instead of:
assert len(preview_data["Sheet1"]) == 2
assert preview_data["Sheet1"].columns.tolist() == ["name", "age"]

# We use:
self._assert_dataframe_structure(actual_df, expected_df)
```

### Robust Test Data Generation

The tests generate data dynamically based on parameters:

```python
# Generate test data with specified structure
csv_data = self._generate_csv_data(rows=3, columns=['name', 'age', 'city'])
excel_data = self._generate_excel_data([
    {'name': 'Users', 'columns': ['name', 'age'], 'rows': 2},
    {'name': 'Products', 'columns': ['product', 'price'], 'rows': 2}
])
```

### Comprehensive Cleanup

Each test automatically cleans up:
- Database records (data sources, projects, datasets)
- Storage files
- Temporary files
- Test artifacts

## Running the Tests

### Prerequisites

1. Install test dependencies:
   ```bash
   pip install -r tests/requirements-test.txt
   ```

2. Ensure you have access to the test Supabase instance
3. Verify test user credentials in `test-cfg.yaml`

### Running Tests

#### Option 1: Using pytest directly
```bash
cd api
pytest tests/test_file_service_integration.py -v
```

#### Option 2: Using the test runner script
```bash
cd api/tests
python run_integration_tests.py
```

#### Option 3: Run specific test methods
```bash
cd api
pytest tests/test_file_service_integration.py::TestFileServiceIntegration::test_file_service_initialization_and_data_retrieval -v
```

#### Option 4: Run with coverage
```bash
cd api
pytest tests/test_file_service_integration.py --cov=services.file_service -v
```

## Test Configuration

The tests use the following configuration from `test-cfg.yaml`:

```yaml
devops:
  creds:
    user: test@oryxintel.com
    pwd: CyAIi74f73hj
```

## Benefits

### Compared to Unit Tests with Mocks

1. **Real Integration Testing**: Tests actual database and storage operations
2. **Dynamic Validation**: Uses test data as source of truth, not hardcoded values
3. **Comprehensive Coverage**: Tests complete workflows, not isolated functions
4. **Better Error Detection**: Catches real integration issues
5. **Maintainable**: Easy to modify test data without breaking assertions

### DRY (Don't Repeat Yourself) Design

1. **Combined Test Methods**: Related functionality tested together
2. **Reusable Helpers**: Shared methods for common operations
3. **Parameterized Data**: Dynamic test data generation
4. **Consistent Patterns**: Same validation approach across all tests

## Troubleshooting

### Common Issues

1. **Authentication Errors**: Verify test user credentials in `test-cfg.yaml`
2. **Database Connection**: Ensure Supabase credentials are properly configured
3. **Storage Access**: Verify bucket permissions for test user
4. **File Cleanup**: Check that temporary files are properly cleaned up

### Debug Mode

Run tests with more verbose output:
```bash
pytest tests/test_file_service_integration.py -v -s --tb=long
```

### Test Isolation

Each test method:
- Creates its own test project
- Uses unique identifiers
- Cleans up all created resources
- Runs independently of other tests

## Extending the Tests

### Adding New Test Cases

1. Add new test methods to `TestFileServiceIntegration`
2. Use existing helper methods for data generation
3. Follow the dynamic validation pattern
4. Ensure proper cleanup in teardown

### Adding New File Types

1. Extend `_generate_test_data()` method
2. Add new test cases to `test_file_processing_workflow_all_formats()`
3. Update validation logic as needed

### Adding New Validation

1. Create new assertion methods following the `_assert_*` pattern
2. Use dynamic validation based on test data
3. Provide clear error messages for failures
