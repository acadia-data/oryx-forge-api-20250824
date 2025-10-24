import httpx
USER_ID = '24d811e2-1801-4208-8030-a86abbda59b8'
PROJECT_ID = 'fd0b6b50-ed50-49db-a3ce-6c7295fb85a2'
USER_ID = '33f8af57-dd3d-4072-a973-429b3d55b926'
PROJECT_ID = '5f4c4e33-4e4e-4a3b-94cd-046be895ccb9'

base_url = "http://localhost:8000"
base_url = "http://127.0.0.1:8000"
base_url = "https://oryx-forge-dev-20250823-846392806260.us-central1.run.app"

# Test Preview
print("Testing Preview...")
preview_response = httpx.post(f"{base_url}/data/load-dataframe", json={
    "user_id": USER_ID,
    "project_id": PROJECT_ID,
    # "name_python": 'exploration.HpiCountByYear'
    # "name_python": 'sources.HpiMasterCsv'
    "name_python": 'sources.NpiExpandedAnnualizedMsa20252Xlsx'
}, timeout=30.0)
print(f"status_code: {preview_response.status_code}")
if preview_response.is_success:
    data = preview_response.json()
    print(f"Found {len(data)} sheets")
else:
    print(f"Error: {preview_response.text}")

