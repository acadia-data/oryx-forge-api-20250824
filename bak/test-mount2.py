import subprocess

# Your PowerShell command
cmd_mount = '''
$rcloneProcess = Start-Process rclone -ArgumentList "mount","oryx-forge-gcs:orxy-forge-datasets-dev/24d811e2-1801-4208-8030-a86abbda59b8/fd0b6b50-ed50-49db-a3ce-6c7295fb85a2","./data","--vfs-cache-mode","writes","--vfs-cache-max-age","24h" -WindowStyle Hidden -PassThru
'''

cmd_mount = '''
$rcloneProcess = Start-Process rclone -ArgumentList "mount","oryx-forge-gcs:orxy-forge-datasets-dev/24d811e2-1801-4208-8030-a86abbda59b8/fd0b6b50-ed50-49db-a3ce-6c7295fb85a2","./data","--vfs-cache-mode","writes","--vfs-cache-max-age","24h" -WindowStyle Hidden -PassThru -Wait

# Check if the process failed
if ($rcloneProcess.ExitCode -ne 0) {
    Write-Host "rclone failed with exit code: $($rcloneProcess.ExitCode)"
}
'''

cmd_unmount = '''
Stop-Process -Id $rcloneProcess.Id -Force
'''
# this doesn't work across runs. instead could save the mount process id

# mount
result = subprocess.run(
    ["powershell", "-Command", cmd_mount],
    capture_output=True,
    text=True
)

print("Return code:", result.returncode)
print("Output:", result.stdout)
print("Errors:", result.stderr)

# unmount
result = subprocess.run(
    ["powershell", "-Command", cmd_unmount],
    capture_output=True,
    text=True
)

print("Return code:", result.returncode)
print("Output:", result.stdout)
print("Errors:", result.stderr)

subprocess.run(["taskkill", "/F", "/IM", "rclone.exe"])
