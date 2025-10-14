import subprocess

rclone_process = subprocess.Popen([
    "rclone",
    "mount",
    "oryx-forge-gcs:orxy-forge-datasets-dev/24d811e2-1801-4208-8030-a86abbda59b8/fd0b6b50-ed50-49db-a3ce-6c7295fb85a2",
    "./data",
    "--vfs-cache-mode", "writes",
    "--vfs-cache-max-age", "24h"
],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    creationflags=subprocess.CREATE_NO_WINDOW
)

# Read output (this will block until process finishes)
stdout, stderr = rclone_process.communicate()

if rclone_process.returncode > 0:
    print('failed mount')
    print(stderr)
else:
    print('successful mount')
    print(stdout)


# Later, when you want to stop it:
rclone_process.terminate()  # Graceful termination
# or
rclone_process.kill()  # Forceful termination


# Unmount the specific mount point
subprocess.run(["rclone", "umount", "./data"])
