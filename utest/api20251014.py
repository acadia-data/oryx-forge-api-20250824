import httpx
USER_ID = '24d811e2-1801-4208-8030-a86abbda59b8'
PROJECT_ID = 'fd0b6b50-ed50-49db-a3ce-6c7295fb85a2'

base_url = "http://localhost:8000"
base_url = "http://127.0.0.1:8000"
# base_url = "https://oryx-forge-dev-20250823-846392806260.us-central1.run.app"

# Test Preview
print("Testing Preview...")
preview_response = httpx.post(f"{base_url}/data/load-dataframe", json={
    "user_id": USER_ID,
    "project_id": PROJECT_ID,
    # "name_python": 'exploration.HpiCountByYear'
    "name_python": 'sources.HpiMasterCsv'
})
print(f"Preview: {preview_response.status_code}")
if preview_response.is_success:
    data = preview_response.json()
    print(f"Found {len(data)} sheets")
else:
    print(f"Error: {preview_response.text}")

