# PowerShell commands for local API development
# Copy and paste these commands into PowerShell

# Set environment variable for local API mount root

cd api
$env:ORYX_MOUNT_ROOT="D:/data/oryx-forge-api/"
uvicorn app:app --reload

uv pip install -r requirements.txt
# has an issue with hardlinking, maybe poetry is better?
uv run uvicorn app:app --reload
uv run uvicorn app:app
