# PowerShell commands for local API development
# Copy and paste these commands into PowerShell

# Set environment variable for local API mount root

Start-Process rclone -ArgumentList "mount","oryx-forge-gcs:orxy-forge-datasets-dev","D:/data/oryx-forge-api/mnt/data","--vfs-cache-mode writes" -WindowStyle Hidden
$env:ORYX_MOUNT_ROOT="D:/data/oryx-forge-api/"
uvicorn api.app:app # --reload
uvicorn app:app # --reload
Stop-Process -Name rclone -Force

# simulate deploy
cd api
uv venv C:\venvs\oryx-forge-api
C:\venvs\oryx-forge-api\Scripts\activate
C:\venvs\oryx-forge-api\Scripts\Activate.ps1
uv pip install -r requirements.txt
uv pip install --no-cache --force-reinstall --no-deps https://storage.googleapis.com/adt-devops-pypi/packages/oryxforge-25.9.8-py3-none-any.whl
uv pip install --force-reinstall --no-cache -r requirements.txt
$env:ORYX_MOUNT_ROOT="D:/data/oryx-forge-api/"
uvicorn app:app --reload


