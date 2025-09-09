import httpx
import adtiam
from supabase import create_client

# Get credentials
adtiam.load_creds('adt-db')
supabase = create_client(adtiam.creds['db']['supabase']['url'], adtiam.creds['db']['supabase']['key-admin'])

# Get user_owner and project_id from database
data_source_id = 'de73a2b6-3c0e-4c8d-b579-7d42715e9da6'
response = supabase.table("data_sources").select("user_owner, project_id").eq("id", data_source_id).execute()
user_owner, project_id = response.data[0]['user_owner'], response.data[0]['project_id']

base_url = "http://localhost:8000"
base_url = "http://127.0.0.1:8000"

# Test Preview
print("Testing Preview...")
preview_response = httpx.post(f"{base_url}/files/preview", json={
    "user_owner": user_owner,
    "project_id": project_id,
    "data_source_id": data_source_id
})
print(f"Preview: {preview_response.status_code}")
if preview_response.is_success:
    data = preview_response.json()
    print(f"Found {len(data)} sheets")

# Test Import
print("\nTesting Import...")
import_response = httpx.post(f"{base_url}/files/import", json={
    "user_owner": user_owner,
    "project_id": project_id,
    "data_source_id": data_source_id,
    "settings_load": {},
    "settings_save": {
        "createNewDataset": True,
        "datasetName": "ADPWNUSNERSA.xlsx",
        "selectedSheets": {"Weekly": "Weekly"}
    }
})
print(f"Import: {import_response.status_code}")
if import_response.is_success:
    result = import_response.json()
    print(f"Created dataset: {result.get('dataset_id')}")
