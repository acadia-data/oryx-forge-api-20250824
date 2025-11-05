# OryxForge Local Development Environment Guide
**Date**: 2025-11-02
**Audience**: Solo founder / API developers
**Goal**: Fast iteration on API without relying on CLI or working UI

---

## Executive Summary

This guide provides a **< 5-minute setup** for local API development with **< 5-second iteration cycles**. Perfect for building and testing the API while the UI is being developed.

**Key Benefits**:
- No CLI dependency - test API directly
- Hot reload - changes apply instantly
- Multiple testing options - choose what fits your workflow
- Production-ready - same environment as GCP deployment

---

## 1. Environment Setup (One-Time)

### 1.1 Directory Structure

Create a local development data directory to replace GCS mount:

```bash
# From project root
mkdir -p dev-data/mnt/data
mkdir -p dev-data/mnt/projects
mkdir -p dev-data/sample-files
```

**Full structure:**
```
oryx-forge-api/
├── api/                    # FastAPI application
├── oryxforge/              # Core services
├── dev-data/               # ← NEW: Local development data
│   ├── mnt/
│   │   ├── data/          # Local "mount point" (replaces GCS)
│   │   │   └── {user_id}/
│   │   │       └── {project_id}/
│   │   │           └── data/
│   │   │               └── *.parquet files
│   │   └── projects/      # Working directories
│   │       └── {user_id}/
│   │           └── {project_id}/
│   │               ├── .oryxforge.cfg
│   │               └── tasks/    # d6tflow tasks (if repo cloned)
│   └── sample-files/      # Test Excel/CSV files
├── .env.local             # ← NEW: Local configuration
└── docs/
    └── planning/
        └── local_dev_environment.md  # ← This file
```

### 1.2 Environment Configuration

Create `.env.local` in project root:

```bash
# API Mode Detection
FASTAPI_ENV=true
ORYX_MOUNT_ROOT=D:/OneDrive/dev/oryx-forge/oryx-forge-api-20250824/dev-data

# Supabase Connection
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-or-service-role-key

# AI API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Test User/Project (for quick testing without parameters)
TEST_USER_ID=24d811e2-1801-4208-8030-a86abbda59b8
TEST_PROJECT_ID=fd0b6b50-ed50-49db-a3ce-6c7295fb85a2
```

**Notes:**
- Use **absolute paths** for `ORYX_MOUNT_ROOT` (Windows: `D:/path`, Linux: `/home/user/path`)
- Get Supabase credentials from Supabase dashboard → Settings → API
- Use test project ID from existing Supabase test data

### 1.3 Credential Management

**Option A: Use environment variables (Recommended for local dev)**

Modify `api/app.py` to support environment variables:

```python
# Top of api/app.py (before other imports)
import os
from pathlib import Path

# Load .env.local for local development
if os.path.exists('.env.local'):
    from dotenv import load_dotenv
    load_dotenv('.env.local')
    print("✓ Loaded .env.local")

# Set FASTAPI_ENV
os.environ['FASTAPI_ENV'] = 'true'

from fastapi import FastAPI, HTTPException
from supabase import create_client

# Initialize Supabase from env vars (with fallback to adtiam)
if os.getenv('SUPABASE_URL'):
    # Local development mode
    cnxn_supabase = create_client(
        os.getenv('SUPABASE_URL'),
        os.getenv('SUPABASE_KEY')
    )
    print("✓ Supabase connected via environment variables")
else:
    # Production mode (GCP)
    import adtiam
    adtiam.load_creds('adt-db')
    adtiam.load_creds('adt-llm')
    cnxn_supabase = create_client(
        adtiam.creds['db']['supabase']['url'],
        adtiam.creds['db']['supabase']['key-admin']
    )
    print("✓ Supabase connected via adtiam")
```

**Option B: Continue using adtiam**

If you prefer to keep using adtiam for consistency:
- Ensure adtiam credentials are configured
- Set `ORYX_MOUNT_ROOT` in `.env.local`
- No changes to `api/app.py` needed

### 1.4 Dependencies

Ensure you have required packages:

```bash
pip install python-dotenv  # For .env.local loading
pip install httpie         # Optional: for CLI testing
```

---

## 2. Running the API Locally

### 2.1 Quick Start

**Start the API with hot reload:**

```bash
# From project root
uvicorn api.app:app --reload --host 0.0.0.0 --port 8000
```

**What you'll see:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345] using StatReload
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
✓ Loaded .env.local
✓ Supabase connected via environment variables
✓ Mount verified at API startup: D:/OneDrive/dev/.../dev-data/mnt/data
INFO:     Application startup complete.
```

**Access the API:**
- API: `http://localhost:8000`
- Interactive Docs: `http://localhost:8000/docs`
- Alternative Docs: `http://localhost:8000/redoc`

### 2.2 Makefile Commands (Optional Enhancement)

Add these commands to your `Makefile`:

```makefile
# === Local Development Commands ===

.PHONY: dev-setup dev-run dev-run-fast dev-test-api dev-clean

# One-time setup
dev-setup:
	@echo "Setting up local development environment..."
	mkdir -p dev-data/mnt/data
	mkdir -p dev-data/mnt/projects
	mkdir -p dev-data/sample-files
	@echo "✓ Development directories created"
	@echo ""
	@echo "Next steps:"
	@echo "1. Copy .env.example to .env.local and configure your credentials"
	@echo "2. Run 'make dev-run' to start the API"
	@echo "3. Open http://localhost:8000/docs to test endpoints"

# Run API with hot reload (recommended for development)
dev-run:
	@echo "Starting OryxForge API with hot reload..."
	@echo "API: http://localhost:8000"
	@echo "Docs: http://localhost:8000/docs"
	@echo ""
	uvicorn api.app:app --reload --host 0.0.0.0 --port 8000

# Run API without reload (faster startup for quick tests)
dev-run-fast:
	@echo "Starting OryxForge API (no reload)..."
	uvicorn api.app:app --host 0.0.0.0 --port 8000

# Test API health
dev-test-api:
	@echo "Testing API endpoints..."
	@echo "\n=== Health Check ==="
	curl -s http://localhost:8000/ | jq .
	@echo "\n=== Environment Check ==="
	curl -s http://localhost:8000/\$$env | jq '{FASTAPI_ENV, ORYX_MOUNT_ROOT}'
	@echo "\n=== LLM Test ==="
	curl -s http://localhost:8000/utest-llm

# Clean development data (be careful!)
dev-clean:
	@echo "⚠️  This will delete all local development data!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		rm -rf dev-data/mnt/data/*; \
		rm -rf dev-data/mnt/projects/*; \
		echo "\n✓ Development data cleaned"; \
	else \
		echo "\n✗ Cancelled"; \
	fi
```

**Usage:**
```bash
make dev-setup   # First time only
make dev-run     # Daily workflow
make dev-test-api # Quick smoke test
```

---

## 3. Testing Without UI: Four Options

### 3.1 Option 1: FastAPI Interactive Docs (⭐ RECOMMENDED)

**Why:** Zero setup, built into FastAPI, perfect for solo developers

**How to use:**

1. Start API: `make dev-run` or `uvicorn api.app:app --reload`
2. Open browser: `http://localhost:8000/docs`
3. You'll see all endpoints with expandable sections

**Example: Testing /data/load-dataframe**

1. Find `POST /data/load-dataframe` in the list
2. Click to expand
3. Click "Try it out" button
4. Fill in the request body:
   ```json
   {
     "user_id": "24d811e2-1801-4208-8030-a86abbda59b8",
     "project_id": "fd0b6b50-ed50-49db-a3ce-6c7295fb85a2",
     "name_python": "sales.Q1"
   }
   ```
5. Click "Execute"
6. See response immediately below:
   ```json
   {
     "headers": ["Product", "Sales"],
     "data": [["Widget A", 1000], ["Widget B", 1500]]
   }
   ```

**Pros:**
- ✅ Zero setup - comes with FastAPI
- ✅ Try any endpoint instantly
- ✅ See request/response schemas
- ✅ Auto-generated from code
- ✅ Perfect for quick iteration

**Cons:**
- ❌ Can't save test cases (have to re-enter data)
- ❌ No scripting/automation

**Best for:** Daily development, trying new endpoints, quick tests

---

### 3.2 Option 2: VS Code REST Client Extension

**Why:** Save test requests as files, one-click execution

**Setup:**

1. Install VS Code extension: "REST Client" by Huachao Mao
2. Create `api/tests/dev-requests.http`

**Example file:**

```http
### Variables
@baseUrl = http://localhost:8000
@userId = 24d811e2-1801-4208-8030-a86abbda59b8
@projectId = fd0b6b50-ed50-49db-a3ce-6c7295fb85a2

### Health Check
GET {{baseUrl}}/
Content-Type: application/json

### Environment Variables
GET {{baseUrl}}/$env
Content-Type: application/json

### Test LLM
GET {{baseUrl}}/utest-llm
Content-Type: application/json

### Load DataFrame - Sales Q1
POST {{baseUrl}}/data/load-dataframe
Content-Type: application/json

{
  "user_id": "{{userId}}",
  "project_id": "{{projectId}}",
  "name_python": "sales.Q1"
}

### Load DataFrame - Customers
POST {{baseUrl}}/data/load-dataframe
Content-Type: application/json

{
  "user_id": "{{userId}}",
  "project_id": "{{projectId}}",
  "name_python": "customers.All"
}

### Chat - Simple Question
POST {{baseUrl}}/llm
Content-Type: application/json

{
  "prompt": "What is the capital of France?"
}

### Chat - Data Analysis
POST {{baseUrl}}/llm
Content-Type: application/json

{
  "prompt": "Analyze the sales trends and identify the top 3 performing products."
}

### File Preview
POST {{baseUrl}}/files/preview
Content-Type: application/json

{
  "user_owner": "{{userId}}",
  "project_id": "{{projectId}}",
  "data_source_id": "your-data-source-id-here"
}

### File Import
POST {{baseUrl}}/files/import
Content-Type: application/json

{
  "user_owner": "{{userId}}",
  "project_id": "{{projectId}}",
  "data_source_id": "your-data-source-id-here",
  "settings_load": {},
  "settings_save": {
    "createNewDataset": true,
    "datasetName": "ImportedData",
    "selectedSheets": {
      "Sheet1": "Sheet1"
    }
  }
}
```

**Usage:**
- Click "Send Request" link above any `###` section
- Response appears inline in VS Code
- Edit and resend instantly
- Variables defined at top

**Pros:**
- ✅ Save test cases as files
- ✅ Version control your tests
- ✅ Variables for reusability
- ✅ One-click execution
- ✅ Response appears in VS Code

**Cons:**
- ❌ Requires VS Code extension
- ❌ Not as visual as /docs

**Best for:** Repeated test cases, team collaboration, regression testing

---

### 3.3 Option 3: Python Test Scripts

**Why:** Automate complex workflows, generate test data

**Create `api/tests/manual_test.py`:**

```python
"""Manual API testing script for quick iteration."""
import requests
import json
import os
from pathlib import Path
from dotenv import load_dotenv

# Load test credentials
load_dotenv('.env.local')

BASE_URL = "http://localhost:8000"
TEST_USER_ID = os.getenv('TEST_USER_ID')
TEST_PROJECT_ID = os.getenv('TEST_PROJECT_ID')


def test_health():
    """Test API health check."""
    print("=== Testing Health Check ===")
    r = requests.get(f"{BASE_URL}/")
    if r.status_code == 200:
        print(f"✓ Health: {r.json()}")
    else:
        print(f"✗ Error: {r.status_code}")


def test_environment():
    """Check environment configuration."""
    print("\n=== Checking Environment ===")
    r = requests.get(f"{BASE_URL}/$env")
    if r.status_code == 200:
        env = r.json()
        print(f"✓ FASTAPI_ENV: {env.get('FASTAPI_ENV')}")
        print(f"✓ ORYX_MOUNT_ROOT: {env.get('ORYX_MOUNT_ROOT')}")
    else:
        print(f"✗ Error: {r.status_code}")


def test_load_dataframe(dataset: str, sheet: str):
    """Test loading a DataFrame."""
    print(f"\n=== Loading DataFrame: {dataset}.{sheet} ===")
    r = requests.post(f"{BASE_URL}/data/load-dataframe", json={
        "user_id": TEST_USER_ID,
        "project_id": TEST_PROJECT_ID,
        "name_python": f"{dataset}.{sheet}"
    })

    if r.status_code == 200:
        data = r.json()
        print(f"✓ Loaded DataFrame:")
        print(f"  Rows: {len(data['data'])}")
        print(f"  Columns: {data['headers']}")
        print(f"  Preview: {data['data'][:3]}")  # First 3 rows
        return data
    else:
        print(f"✗ Error: {r.status_code} - {r.text}")
        return None


def test_chat_streaming(prompt: str):
    """Test streaming chat response."""
    print(f"\n=== Chat: {prompt[:50]}... ===")
    r = requests.post(f"{BASE_URL}/llm", json={"prompt": prompt}, stream=True)

    if r.status_code == 200:
        print("Response: ", end="", flush=True)
        for line in r.iter_lines():
            if line:
                content = line.decode('utf-8').replace('data: ', '')
                if content != '[DONE]':
                    print(content, end="", flush=True)
        print("\n✓ Chat complete")
    else:
        print(f"✗ Error: {r.status_code}")


def test_workflow_import_to_chat():
    """Test complete workflow: import → load → chat."""
    print("\n=== Testing Complete Workflow ===")

    # Step 1: Load existing data
    print("\n1. Loading sales data...")
    df = test_load_dataframe("sales", "Q1")

    if df:
        # Step 2: Analyze with chat
        print("\n2. Analyzing with Claude...")
        test_chat_streaming("Summarize the sales data in one sentence.")

        print("\n✓ Workflow complete")
    else:
        print("\n✗ Workflow failed: Could not load data")


if __name__ == "__main__":
    print("=" * 60)
    print("OryxForge API Manual Testing")
    print("=" * 60)

    # Run tests
    test_health()
    test_environment()

    # Test data operations
    test_load_dataframe("sales", "Q1")

    # Test chat
    test_chat_streaming("What is 2+2?")

    # Test complete workflow
    test_workflow_import_to_chat()

    print("\n" + "=" * 60)
    print("Testing complete!")
    print("=" * 60)
```

**Run:**
```bash
python api/tests/manual_test.py
```

**Output:**
```
============================================================
OryxForge API Manual Testing
============================================================
=== Testing Health Check ===
✓ Health: {'message': 'Oryx Forge API'}

=== Checking Environment ===
✓ FASTAPI_ENV: true
✓ ORYX_MOUNT_ROOT: D:/OneDrive/dev/.../dev-data

=== Loading DataFrame: sales.Q1 ===
✓ Loaded DataFrame:
  Rows: 100
  Columns: ['Product', 'Q1_Sales', 'Q2_Sales']
  Preview: [['Widget A', 1000, 1100], ['Widget B', 1500, 1400], ...]

...
```

**Pros:**
- ✅ Full Python power - generate data, complex assertions
- ✅ Automated testing
- ✅ Test multi-step workflows
- ✅ Easy to run from CLI

**Cons:**
- ❌ Requires writing code
- ❌ Slower to iterate vs /docs

**Best for:** Complex workflows, test data generation, CI/CD integration

---

### 3.4 Option 4: HTTPie (CLI Tool)

**Why:** Clean, human-friendly CLI for API testing

**Install:**
```bash
pip install httpie
```

**Usage:**

```bash
# Health check
http GET localhost:8000/

# Environment check
http GET localhost:8000/\$env

# Load DataFrame
http POST localhost:8000/data/load-dataframe \
  user_id="24d811e2-1801-4208-8030-a86abbda59b8" \
  project_id="fd0b6b50-ed50-49db-a3ce-6c7295fb85a2" \
  name_python="sales.Q1"

# Chat
http POST localhost:8000/llm prompt="Explain quantum computing in simple terms"

# With headers
http POST localhost:8000/data/load-dataframe \
  Content-Type:application/json \
  user_id="24d811e2-1801-4208-8030-a86abbda59b8" \
  project_id="fd0b6b50-ed50-49db-a3ce-6c7295fb85a2" \
  name_python="sales.Q1"
```

**Output:**
```
HTTP/1.1 200 OK
content-type: application/json

{
    "headers": ["Product", "Sales"],
    "data": [
        ["Widget A", 1000],
        ["Widget B", 1500]
    ]
}
```

**Pros:**
- ✅ Beautiful colored output
- ✅ Automatic JSON formatting
- ✅ Simpler syntax than curl
- ✅ Good for terminal workflow

**Cons:**
- ❌ Requires separate tool
- ❌ Less visual than /docs

**Best for:** Terminal-centric developers, scripting, quick CLI tests

---

## 4. Rapid Iteration Workflow

### 4.1 The 5-Second Loop

**Goal:** Edit code → see result in < 5 seconds

**Setup:**
1. Terminal 1: `make dev-run` (API with hot reload)
2. Browser: Open `http://localhost:8000/docs`

**Workflow:**

```
1. Edit api/app.py or oryxforge/services/*.py
   ⏱️ 30 seconds

2. Save file (Ctrl+S)
   ⏱️ 0 seconds

3. Uvicorn auto-reloads
   ⏱️ 1-2 seconds

4. Click "Execute" in /docs
   ⏱️ 1 second

5. See result
   ⏱️ 1 second

Total: < 5 seconds from save to result
```

**No restart, no rebuild, no CLI commands needed.**

### 4.2 Example: Adding a New Endpoint

**Scenario:** Add endpoint to list all datasets for a user

**Step 1: Add endpoint to `api/app.py`**

```python
from pydantic import BaseModel

class ListDatasetsRequest(BaseModel):
    user_id: str
    project_id: str

@app.post("/datasets/list")
def list_datasets(request: ListDatasetsRequest):
    """
    List all datasets for a user and project.

    Returns dataset names, IDs, and creation dates.
    """
    from oryxforge.services.project_service import ProjectService
    from oryxforge.services.env_config import ProjectContext

    # Set context (no config file needed)
    ProjectContext.set(
        user_id=request.user_id,
        project_id=request.project_id,
        write_config=False
    )

    # Get datasets
    project_service = ProjectService(
        project_id=request.project_id,
        user_id=request.user_id,
        mount_ensure=False  # Don't check mount for listing
    )

    datasets = project_service.get_datasets()

    # Clean up context
    ProjectContext.clear()

    return {
        "datasets": datasets,
        "count": len(datasets)
    }
```

**Step 2: Save file**
- Ctrl+S
- Watch terminal: "Reloading..."

**Step 3: Test in /docs**
- Refresh `http://localhost:8000/docs`
- Find new endpoint `POST /datasets/list`
- Click "Try it out"
- Enter:
  ```json
  {
    "user_id": "24d811e2-1801-4208-8030-a86abbda59b8",
    "project_id": "fd0b6b50-ed50-49db-a3ce-6c7295fb85a2"
  }
  ```
- Click "Execute"
- See result:
  ```json
  {
    "datasets": [
      {
        "id": "abc-123",
        "name": "Sales Data",
        "created_at": "2025-11-02T10:30:00Z"
      }
    ],
    "count": 1
  }
  ```

**Total time:** < 30 seconds from idea to working endpoint

### 4.3 Debugging Strategy

**See Logs in Real-Time**

The terminal running `make dev-run` shows:
- All HTTP requests (method, path, status code)
- Your `logger.debug/info/error` messages
- Exception tracebacks with line numbers
- Timing information

**Add Debug Logging:**

```python
from loguru import logger

@app.post("/data/load-dataframe")
def load_dataframe(request: DataFrameLoadRequest):
    logger.debug(f"Request received: {request.name_python}")
    logger.debug(f"User: {request.user_id}, Project: {request.project_id}")

    try:
        # Your code here
        ProjectService.project_init(request.project_id, request.user_id)
        logger.info(f"Project initialized successfully")

        df = io_service.load_df_pd(request.name_python)
        logger.success(f"DataFrame loaded: {len(df)} rows, {len(df.columns)} cols")

        return formatted_data

    except Exception as e:
        logger.error(f"Failed to load DataFrame: {e}")
        raise
```

**Inspect Environment State:**

Use the `/$env` endpoint to debug environment issues:

```bash
curl http://localhost:8000/\$env | jq '{
  FASTAPI_ENV,
  ORYX_MOUNT_ROOT,
  GOOGLE_CLOUD_PROJECT,
  SUPABASE_URL,
  TEST_USER_ID
}'
```

**Common Issues:**

| Problem | Check | Solution |
|---------|-------|----------|
| Mount not found | `/$env` → ORYX_MOUNT_ROOT | Set in .env.local, use absolute path |
| Supabase connection error | `/$env` → SUPABASE_URL | Set credentials in .env.local |
| Config file not found | Check working_dir in logs | Use mount_ensure=False for testing |
| Permission denied | Check mount directory permissions | mkdir -p dev-data/mnt/data |

---

## 5. Sample Data Setup

### 5.1 Create Test Files

**Create sample Excel file:**

```python
# dev-scripts/create_sample_data.py
import pandas as pd
from pathlib import Path

# Create dev-data/sample-files directory
sample_dir = Path('dev-data/sample-files')
sample_dir.mkdir(parents=True, exist_ok=True)

# Sales data
df_sales = pd.DataFrame({
    'Product': ['Widget A', 'Widget B', 'Widget C', 'Widget D', 'Widget E'],
    'Q1_Sales': [1000, 1500, 1200, 800, 2000],
    'Q2_Sales': [1100, 1400, 1300, 900, 2100],
    'Q3_Sales': [1050, 1550, 1250, 850, 2050],
    'Q4_Sales': [1200, 1600, 1400, 950, 2200]
})

# Customers data
df_customers = pd.DataFrame({
    'CustomerID': [1, 2, 3, 4, 5],
    'Name': ['Acme Corp', 'TechStart', 'BigCo', 'SmallBiz', 'MegaCorp'],
    'Industry': ['Manufacturing', 'Technology', 'Retail', 'Services', 'Finance'],
    'Revenue': [1000000, 500000, 2000000, 250000, 5000000]
})

# Save to Excel (multi-sheet)
with pd.ExcelWriter(sample_dir / 'sales_data.xlsx') as writer:
    df_sales.to_excel(writer, sheet_name='Q1', index=False)
    df_sales.to_excel(writer, sheet_name='Q2', index=False)
    df_sales.to_excel(writer, sheet_name='Summary', index=False)

# Save customers as CSV
df_customers.to_csv(sample_dir / 'customers.csv', index=False)

print("✓ Sample files created:")
print(f"  - {sample_dir / 'sales_data.xlsx'}")
print(f"  - {sample_dir / 'customers.csv'}")
```

**Run:**
```bash
python dev-scripts/create_sample_data.py
```

### 5.2 Seed Supabase Test Data

**Create test project and datasets:**

```python
# dev-scripts/seed_supabase.py
import os
import pandas as pd
from pathlib import Path
from supabase import create_client
from dotenv import load_dotenv

load_dotenv('.env.local')

# Connect to Supabase
supabase = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_KEY')
)

TEST_USER_ID = os.getenv('TEST_USER_ID')
TEST_PROJECT_ID = os.getenv('TEST_PROJECT_ID')

# 1. Create test project (if not exists)
existing_project = supabase.table('projects').select('*').eq('id', TEST_PROJECT_ID).execute()

if not existing_project.data:
    project = supabase.table('projects').insert({
        'id': TEST_PROJECT_ID,
        'name': 'Test Project',
        'user_owner': TEST_USER_ID
    }).execute()
    print(f"✓ Created test project: {TEST_PROJECT_ID}")
else:
    print(f"✓ Test project already exists: {TEST_PROJECT_ID}")

# 2. Create test dataset
dataset = supabase.table('datasets').insert({
    'name': 'Sales Data',
    'name_python': 'sales',
    'project_id': TEST_PROJECT_ID,
    'user_owner': TEST_USER_ID
}).execute()

dataset_id = dataset.data[0]['id']
print(f"✓ Created dataset: {dataset_id}")

# 3. Create sample Parquet file and datasheet record
df = pd.DataFrame({
    'Product': ['Widget A', 'Widget B', 'Widget C'],
    'Sales': [1000, 1500, 1200]
})

# Save to local mount
parquet_dir = Path('dev-data/mnt/data') / TEST_USER_ID / TEST_PROJECT_ID / 'data' / dataset_id
parquet_dir.mkdir(parents=True, exist_ok=True)
parquet_file = parquet_dir / 'Q1.parquet'
df.to_parquet(parquet_file)

print(f"✓ Created Parquet file: {parquet_file}")

# 4. Create datasheet record
sheet = supabase.table('datasheets').insert({
    'name': 'Q1 Sales',
    'name_python': 'Q1',
    'dataset_id': dataset_id,
    'type': 'dataframe',
    'uri': f'file://{parquet_file}',
    'user_owner': TEST_USER_ID
}).execute()

print(f"✓ Created datasheet: {sheet.data[0]['id']}")

print("\n=== Test Data Ready ===")
print(f"User ID: {TEST_USER_ID}")
print(f"Project ID: {TEST_PROJECT_ID}")
print(f"Dataset: sales")
print(f"Sheet: Q1")
print(f"\nTest API with:")
print(f'  POST /data/load-dataframe')
print(f'  {{"user_id": "{TEST_USER_ID}", "project_id": "{TEST_PROJECT_ID}", "name_python": "sales.Q1"}}')
```

**Run:**
```bash
python dev-scripts/seed_supabase.py
```

---

## 6. Recommended Daily Workflow

### 6.1 For Solo Founder Building UI

**Morning Setup (< 1 minute):**

```bash
cd oryx-forge-api
make dev-run
```

Leave this terminal running all day.

**Development Workflow:**

```
┌─────────────────────────────────────────────┐
│ VS Code: Edit api/app.py                    │
│   - Add/modify endpoints                    │
│   - Update service logic                    │
│   - Fix bugs                                │
└─────────────────────────────────────────────┘
              ↓ (Save: Ctrl+S)
┌─────────────────────────────────────────────┐
│ Terminal: Uvicorn auto-reloads              │
│   - Watches for file changes                │
│   - Reloads in 1-2 seconds                  │
│   - Shows any errors immediately            │
└─────────────────────────────────────────────┘
              ↓ (< 2 seconds)
┌─────────────────────────────────────────────┐
│ Browser: Test at localhost:8000/docs        │
│   - Click endpoint to test                  │
│   - Fill in request data                    │
│   - Execute and see response                │
│   - Iterate immediately if needed           │
└─────────────────────────────────────────────┘
```

**Total cycle time: < 5 seconds per iteration**

### 6.2 What to Use

**For Solo Development:**

| Task | Tool | Why |
|------|------|-----|
| **Daily testing** | FastAPI /docs | Zero setup, instant feedback |
| **Repeated tests** | REST Client | Save requests, one-click rerun |
| **Complex workflows** | Python scripts | Multi-step tests, automation |
| **Quick CLI checks** | HTTPie | Beautiful terminal output |

### 6.3 What NOT to Use

**Avoid these tools for solo development:**

| Tool | Why Skip It |
|------|-------------|
| ❌ Postman | Overkill, separate app, slower workflow |
| ❌ CLI testing | You're removing CLI anyway, don't build new CLI test infrastructure |
| ❌ Writing integration tests first | Premature optimization - slows you down before you have working UI |
| ❌ Docker for local dev | Adds complexity, slower iteration |

**Rule of thumb:** If it takes > 10 seconds to test a change, it's too slow.

### 6.4 When UI is Ready

**No backend changes needed!**

```javascript
// Your Next.js/React frontend
const API_URL = 'http://localhost:8000'

// Load data
const response = await fetch(`${API_URL}/data/load-dataframe`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    user_id: userId,
    project_id: projectId,
    name_python: 'sales.Q1'
  })
})

const data = await response.json()
// { headers: [...], data: [[...], [...]] }
```

Same API, same endpoints, no changes needed.

---

## 7. Quick Reference

### 7.1 Common Commands

```bash
# Start API (hot reload)
make dev-run
# or
uvicorn api.app:app --reload --host 0.0.0.0 --port 8000

# Start API (no reload, faster)
uvicorn api.app:app --host 0.0.0.0 --port 8000

# Test API health
curl http://localhost:8000/ | jq .

# Check environment
curl http://localhost:8000/\$env | jq .

# Run Python test script
python api/tests/manual_test.py

# Create sample data
python dev-scripts/create_sample_data.py

# Seed Supabase
python dev-scripts/seed_supabase.py
```

### 7.2 Key URLs

| URL | Purpose |
|-----|---------|
| `http://localhost:8000` | API root |
| `http://localhost:8000/docs` | Interactive API documentation (Swagger UI) |
| `http://localhost:8000/redoc` | Alternative API documentation (ReDoc) |
| `http://localhost:8000/$env` | View all environment variables |
| `http://localhost:8000/utest-llm` | Quick LLM connectivity test |

### 7.3 Test Credentials

```bash
# From .env.local
TEST_USER_ID=24d811e2-1801-4208-8030-a86abbda59b8
TEST_PROJECT_ID=fd0b6b50-ed50-49db-a3ce-6c7295fb85a2

# Use in API requests
{
  "user_id": "24d811e2-1801-4208-8030-a86abbda59b8",
  "project_id": "fd0b6b50-ed50-49db-a3ce-6c7295fb85a2",
  "name_python": "sales.Q1"
}
```

### 7.4 API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Health check |
| `/$env` | GET | Environment variables |
| `/utest-llm` | GET | Test LLM connection |
| `/llm` | POST | Chat with Claude (streaming) |
| `/data/load-dataframe` | POST | Load DataFrame from storage |
| `/files/preview` | POST | Preview uploaded file |
| `/files/import` | POST | Import file to storage |
| `/profile/set` | POST | Set user profile |

---

## 8. Troubleshooting

### 8.1 Common Issues

**Problem: API won't start - "ORYX_MOUNT_ROOT not set"**

```
ValueError: ORYX_MOUNT_ROOT environment variable must be set
```

**Solution:**
1. Check `.env.local` exists in project root
2. Verify `ORYX_MOUNT_ROOT` is set with absolute path
3. Restart API: `make dev-run`

---

**Problem: "Mount point not accessible"**

```
ValueError: Mount point not accessible: D:/dev-data/mnt/data
```

**Solution:**
1. Create directory: `mkdir -p dev-data/mnt/data`
2. Check path is absolute, not relative
3. Verify permissions (should be writable)

---

**Problem: Supabase connection error**

```
Error: Unable to connect to Supabase
```

**Solution:**
1. Check `.env.local` has `SUPABASE_URL` and `SUPABASE_KEY`
2. Verify credentials in Supabase dashboard → Settings → API
3. Test connection: `curl http://localhost:8000/utest-llm`

---

**Problem: Hot reload not working**

Changes to code don't reflect in API

**Solution:**
1. Check you're running with `--reload` flag
2. Ensure you're editing the right file (not a copy)
3. Watch terminal for "Reloading..." message
4. If still broken, restart: Ctrl+C then `make dev-run`

---

**Problem: Can't access /docs**

Browser shows "This site can't be reached"

**Solution:**
1. Check API is running: look for "Uvicorn running on..." in terminal
2. Try `http://localhost:8000/` (without /docs) first
3. Check firewall isn't blocking port 8000
4. Try `http://127.0.0.1:8000/docs` instead

---

### 8.2 Debug Checklist

When something breaks, check in this order:

```
☐ Is API running? (Check terminal)
☐ Are there errors in terminal? (Read the traceback)
☐ Is .env.local configured? (Check ORYX_MOUNT_ROOT, SUPABASE_URL)
☐ Do dev-data directories exist? (mkdir -p dev-data/mnt/data)
☐ Can you hit health check? (curl http://localhost:8000/)
☐ Check environment: (curl http://localhost:8000/$env | jq .)
☐ Is Supabase accessible? (Check SUPABASE_URL in browser)
☐ Are test user/project valid? (Check Supabase dashboard)
```

---

## 9. Next Steps

### 9.1 Once This is Working

After you can successfully iterate on the API:

1. **Start UI Development**
   - Point UI to `http://localhost:8000`
   - Use existing API endpoints
   - No backend changes needed

2. **Add New Endpoints as Needed**
   - Add to `api/app.py`
   - Test in `/docs`
   - Update UI to consume

3. **Iterate Quickly**
   - Backend and frontend in parallel
   - Test integration continuously
   - Deploy when ready

### 9.2 Before Deployment

Checklist before deploying to production:

```
☐ Remove or secure /$env endpoint (exposes environment vars)
☐ Set up proper authentication (not just test user ID)
☐ Configure CORS for your UI domain only (not allow_origins=["*"])
☐ Set up monitoring and logging (Sentry, LogDNA, etc.)
☐ Test with production Supabase instance
☐ Set up CI/CD pipeline
☐ Document new endpoints added during development
```

---

## Summary

**You now have:**
- ✅ 5-minute setup for local API development
- ✅ < 5-second iteration cycle
- ✅ Multiple testing options (pick what fits your style)
- ✅ No CLI dependency
- ✅ Production-ready environment

**Your workflow:**
```bash
make dev-run                    # Start API
# Open http://localhost:8000/docs in browser
# Edit → Save → Test → Iterate
```

**This lets you move fast and ship UI.**

---

## Appendix: Alternative Configurations

### A. Using Docker (Optional)

If you prefer containerized development:

**Create `docker-compose.yml`:**

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - .:/app
      - ./dev-data:/app/dev-data
    env_file:
      - .env.local
    command: uvicorn api.app:app --reload --host 0.0.0.0 --port 8000
```

**Run:**
```bash
docker-compose up
```

**Pro:** Consistent environment
**Con:** Slower iteration (container overhead)

### B. Using Poetry (Optional)

If you prefer Poetry for dependency management:

```bash
# Setup
poetry install

# Run API
poetry run uvicorn api.app:app --reload
```

### C. Multiple Python Versions

If you need to test across Python versions:

```bash
# Using pyenv
pyenv install 3.12
pyenv local 3.12

# Create venv
python -m venv venv-312
source venv-312/bin/activate  # or venv-312\Scripts\activate on Windows
```

---

**Questions or issues?** Check the troubleshooting section or ask for help in team chat.
