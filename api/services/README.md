# Services Layer

This directory contains the business logic services that have been extracted from the API endpoints to improve testability and maintainability.

## FileService

The `FileService` class handles all file-related operations including:
- Retrieving data source records from Supabase
- Downloading files from Supabase storage
- Reading and parsing different file types (CSV, Excel, Parquet)
- Cleaning up temporary files

### Usage

#### Direct Service Usage

```python
from services.file_service import FileService
from supabase import create_client

# Create service instance
supabase_client = create_client(url, key)
file_service = FileService(supabase_client)

# Use the service directly
try:
    preview_data = file_service.preview_file("your-file-id")
    print(preview_data)
except ValueError as e:
    print(f"Business logic error: {e}")
```

#### Individual Method Usage

```python
# Get data source record
source_record = file_service.get_data_source_record("file-id")

# Download file
file_path = file_service.download_file("file-id", "/data/directory")

# Read file preview
preview = file_service.read_file_preview(file_path, "csv")

# Clean up
file_service.cleanup_file(file_path)
```

### Testing

The service can be easily tested using mocks:

```python
import pytest
from unittest.mock import Mock, patch
from services.file_service import FileService

def test_file_service():
    mock_supabase = Mock()
    file_service = FileService(mock_supabase)
    
    # Test individual methods with mocked dependencies
    # See tests/test_file_service.py for complete examples
```

### Benefits of the Service Layer

1. **Testability**: Business logic can be tested independently of the API layer
2. **Reusability**: Service methods can be called from other parts of the application
3. **Maintainability**: Business logic is centralized and easier to modify
4. **Separation of Concerns**: API layer handles HTTP concerns, service layer handles business logic
5. **Error Handling**: Business logic errors are clearly separated from HTTP errors

### Error Handling

The service layer uses `ValueError` for business logic errors:
- File not found
- Unsupported file types
- Invalid data

The API layer converts these to appropriate HTTP status codes:
- 404 for "not found" errors
- 400 for "bad request" errors
- 500 for unexpected errors

### Configuration

The service accepts configuration through its constructor:
- `supabase_client`: Required Supabase client instance
- `bucket_name`: Optional bucket name (defaults to "data-source-files")
