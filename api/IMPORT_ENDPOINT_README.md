# File Import and Preview Endpoints Documentation

## Overview

The API provides two main endpoints for working with data sources:
- `/files/preview` - Preview data from a data source
- `/files/import` - Import data from a data source to Google Cloud Storage

Both endpoints use the same consistent parameter structure and follow DRY principles.

## Architecture

### DRY Design Pattern

The API follows the DRY (Don't Repeat Yourself) principle through:

1. **Base Request Model**: `BaseFileRequest` contains common parameters
2. **Inheritance**: Both endpoint models inherit from the base class
3. **Service Constructor**: `FileService` stores common parameters to avoid repetition

```python
# Base model with common parameters
class BaseFileRequest(BaseModel):
    user_owner: str
    project_id: str
    data_source_id: str

# Preview endpoint inherits base parameters
class FilePreviewRequest(BaseFileRequest):
    pass

# Import endpoint inherits base parameters + additional settings
class FileImportRequest(BaseFileRequest):
    settings_load: dict
    settings_save: dict
```

## Endpoints

### 1. Preview Endpoint
```
POST /files/preview
```

### 2. Import Endpoint
```
POST /files/import
```

## Request Format

### Common Parameters

Both endpoints accept the same base parameters through inheritance:

```json
{
  "user_owner": "8011f60b-cc9d-4964-8ba7-7368aad37dd7",
  "project_id": "144e9656-91a1-4a4c-9e8a-a02c9a69401f",
  "data_source_id": "be7a7605-807e-41ca-905e-4b50f1bfb1ab"
}
```

### Field Descriptions

- **user_owner**: UUID of the user who owns the operation
- **project_id**: UUID of the project to associate with the operation
- **data_source_id**: UUID of the data source to operate on

### Preview Endpoint Request

```json
{
  "user_owner": "8011f60b-cc9d-4964-8ba7-7368aad37dd7",
  "project_id": "144e9656-91a1-4a4c-9e8a-a02c9a69401f",
  "data_source_id": "be7a7605-807e-41ca-905e-4b50f1bfb1ab"
}
```

### Import Endpoint Request

```json
{
  "user_owner": "8011f60b-cc9d-4964-8ba7-7368aad37dd7",
  "project_id": "144e9656-91a1-4a4c-9e8a-a02c9a69401f",
  "data_source_id": "be7a7605-807e-41ca-905e-4b50f1bfb1ab",
  "settings_load": {},
  "settings_save": {
    "createNewDataset": true,
    "datasetName": "odce_spreadsheet_20252.xlsx",
    "selectedSheets": {
      "ODCE_Returns_VW": "ODCE_Returns_VW",
      "ODCE_Returns_EW": "ODCE_Returns_EW",
      "Exp_Prop_RegionDiversification": "Exp_Prop_RegionDiversification",
      "PropType_ RegionDiversification": "PropType_ RegionDiversification",
      "ODCE_Annualized_VW": "ODCE_Annualized_VW",
      "ODCE_Annualized_EW": "ODCE_Annualized_EW"
    }
  }
}
```

### Import Settings

- **settings_load**: Additional loading settings (currently unused)
- **settings_save**: Configuration for saving the imported data
  - **createNewDataset**: Boolean indicating whether to create a new dataset
  - **datasetName**: Name for the new dataset (required if createNewDataset is true)
  - **selectedSheets**: Mapping of source sheet names to target datasheet names

## Supported File Types

- **CSV**: Single datasheet import (first selected sheet name used as target)
- **Excel**: Multiple sheet import with custom mapping
- **Parquet**: Single datasheet import (first selected sheet name used as target)

## Process Flow

### Preview Process
1. **Data Source Retrieval**: Gets the data source record from Supabase
2. **File Download**: Downloads the file from Supabase storage
3. **Data Processing**: Reads the file and returns preview data (first 100 rows)
4. **Cleanup**: Removes temporary local files

### Import Process
1. **File Retrieval**: Downloads the file from Supabase storage
2. **Data Processing**: Reads the file based on selected sheets and file type
3. **GCS Storage**: Saves each datasheet as a parquet file to Google Cloud Storage
4. **Record Creation**: Creates/updates Supabase records for datasets and datasheets
5. **Status Update**: Updates the data source status to 'ready'
6. **Cleanup**: Removes temporary local files

## GCS Storage Path

Files are saved to GCS using the following path structure:
```
gcs://orxy-forge-datasets-dev/{project_id}/{dataset_id}/{datasheet_name}.parquet
```

## Response Format

### Preview Response

```json
{
  "ODCE_Returns_VW": {
    "headers": ["Date", "Return", "Cumulative"],
    "data": [["2025-01-01", 0.05, 1.05], ["2025-01-02", 0.02, 1.07]]
  },
  "ODCE_Returns_EW": {
    "headers": ["Date", "Return", "Cumulative"],
    "data": [["2025-01-01", 0.03, 1.03], ["2025-01-02", 0.01, 1.04]]
  }
}
```

### Import Response

```json
{
  "status": "success",
  "dataset_id": "new-dataset-uuid",
  "datasheet_ids": {
    "ODCE_Returns_VW": "datasheet-uuid-1",
    "ODCE_Returns_EW": "datasheet-uuid-2",
    "Exp_Prop_RegionDiversification": "datasheet-uuid-3",
    "PropType_ RegionDiversification": "datasheet-uuid-4",
    "ODCE_Annualized_VW": "datasheet-uuid-5",
    "ODCE_Annualized_EW": "datasheet-uuid-6"
  },
  "message": "Successfully imported 6 datasheets"
}
```

### Error Responses

- **400 Bad Request**: Invalid request parameters or unsupported file type
- **404 Not Found**: Data source not found
- **500 Internal Server Error**: GCS access issues or other server errors

## Dependencies

- **gcsfs**: Google Cloud Storage filesystem interface
- **pandas**: Data processing and file reading
- **supabase**: Database operations

## Authentication

The endpoints require:
- Valid Supabase client with admin privileges
- GCS credentials (typically set via environment variables or service account)

## Example Usage

### Python Client - Preview

```python
import requests

url = "https://your-api-domain.com/files/preview"
payload = {
    "user_owner": "8011f60b-cc9d-4964-8ba7-7368aad37dd7",
    "project_id": "144e9656-91a1-4a4c-9e8a-a02c9a69401f",
    "data_source_id": "be7a7605-807e-41ca-905e-4b50f1bfb1ab"
}

response = requests.post(url, json=payload)
preview_data = response.json()
print(f"Preview data: {len(preview_data)} sheets")
```

### Python Client - Import

```python
import requests

url = "https://your-api-domain.com/files/import"
payload = {
    "user_owner": "8011f60b-cc9d-4964-8ba7-7368aad37dd7",
    "project_id": "144e9656-91a1-4a4c-9e8a-a02c9a69401f",
    "data_source_id": "be7a7605-807e-41ca-905e-4b50f1bfb1ab",
    "settings_load": {},
    "settings_save": {
        "createNewDataset": True,
        "datasetName": "odce_spreadsheet_20252.xlsx",
        "selectedSheets": {
            "ODCE_Returns_VW": "ODCE_Returns_VW",
            "ODCE_Returns_EW": "ODCE_Returns_EW"
        }
    }
}

response = requests.post(url, json=payload)
result = response.json()
print(f"Import completed: {result['message']}")
```

### cURL - Preview

```bash
curl -X POST "https://your-api-domain.com/files/preview" \
  -H "Content-Type: application/json" \
  -d '{
    "user_owner": "8011f60b-cc9d-4964-8ba7-7368aad37dd7",
    "project_id": "144e9656-91a1-4a4c-9e8a-a02c9a69401f",
    "data_source_id": "be7a7605-807e-41ca-905e-4b50f1bfb1ab"
  }'
```

### cURL - Import

```bash
curl -X POST "https://your-api-domain.com/files/import" \
  -H "Content-Type: application/json" \
  -d '{
    "user_owner": "8011f60b-cc9d-4964-8ba7-7368aad37dd7",
    "project_id": "144e9656-91a1-4a4c-9e8a-a02c9a69401f",
    "data_source_id": "be7a7605-807e-41ca-905e-4b50f1bfb1ab",
    "settings_load": {},
    "settings_save": {
      "createNewDataset": true,
      "datasetName": "odce_spreadsheet_20252.xlsx",
      "selectedSheets": {
        "ODCE_Returns_VW": "ODCE_Returns_VW",
        "ODCE_Returns_EW": "ODCE_Returns_EW"
      }
    }
  }'
```

## Notes

- Both endpoints automatically handle file cleanup after processing
- GCS bucket access is validated during service initialization
- All database operations use upsert to handle existing records gracefully
- File type detection is based on the data source record's 'type' field
- The preview endpoint returns the first 100 rows of each sheet for quick data inspection
- The import endpoint processes the full dataset and saves to GCS
- **DRY Principle**: Common parameters are defined once in the base model and inherited by both endpoints
- **Service Design**: FileService stores common parameters in the constructor to avoid repetition in method calls
