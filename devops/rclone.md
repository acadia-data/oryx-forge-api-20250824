# problems

* because of the local cache, it might work with old files when they are changed in gcs through an external process
  *   --vfs-cache-mode writes => reads will always be fresh (but slower)
* writes to gcs are also delayed by 5 secs --vfs-cache-mode writes:bash--vfs-write-back 5s 
  * will that mean old data is displayed in the front end? => not if i run another agent to summarize, that will typically take longer than 5 secs. user can also refresh.

# install

## local windows

(installs in path)
winget install Rclone.Rclone
winget install WinFsp.WinFsp
winget install --id=NSSM.NSSM  -e

**finding the rclone path**
where rclone
Get-Command rclone | Select-Object -ExpandProperty Source
C:\Users\deepmind\AppData\Local\Microsoft\WinGet\Links\rclone.exe
C:\Users\deepmind\AppData\Roaming\rclone\rclone.conf

# config

[oryx-forge-gcs]
type = google cloud storage
object_acl = bucketOwnerRead
location = us-central1
bucket_policy_only = true


copy devops\rclone.conf C:\Users\deepmind\AppData\Roaming\rclone\rclone.conf

**test**
rclone ls oryx-forge-gcs:orxy-forge-datasets-dev

## useful commands

**show config**
rclone config file

**authenticate existing config**
rclone config reconnect oryx-forge-gcs:

rclone authorize "google cloud storage"
This last command is useful when configuring rclone on a headless server - you run it on a machine with a browser, and it gives you a token to paste into your headless server's config.

token also works across machines

# mount

## config

rclone mount mygcs:bucket ./data --config "D:\project\rclone.conf"

rclone mount oryx-forge-gcs:orxy-forge-datasets-dev/24d811e2-1801-4208-8030-a86abbda59b8/fd0b6b50-ed50-49db-a3ce-6c7295fb85a2 ./data --vfs-cache-mode writes  --vfs-cache-max-age 24h
user_id = 24d811e2-1801-4208-8030-a86abbda59b8
project_id = fd0b6b50-ed50-49db-a3ce-6c7295fb85a2
--vfs-cache-mode full
--gcs-bucket-policy-only 
--daemon

rclone mount oryxgcs:orxy-forge-datasets-dev/d6tflow/data/TaskTest ./data --gcs-bucket-policy-only  --vfs-cache-mode writes

## local windows

### powershell

**start**
Start-Process rclone -ArgumentList "mount","remote:path","X:" -WindowStyle Hidden
Stop-Process -Name rclone -Force

**start mount**
$rcloneProcess = Start-Process rclone -ArgumentList "mount","oryx-forge-gcs:orxy-forge-datasets-dev/24d811e2-1801-4208-8030-a86abbda59b8/fd0b6b50-ed50-49db-a3ce-6c7295fb85a2","./data","--vfs-cache-mode","writes","--vfs-cache-max-age","24h" -WindowStyle Hidden -PassThru

**stop mount**
Stop-Process -Id $rcloneProcess.Id -Force


### nssm

kind of annoying because can't just mount any random folder

nssm install rclone-mount "C:\Users\deepmind\AppData\Local\Microsoft\WinGet\Links\rclone.exe" "mount remote:path X: --vfs-cache-mode full"
nssm install rclone "C:\Program Files\rclone\rclone.exe" mount remote:path X: --vfs-cache-mode full
nssm start rclone-mount
nssm stop rclone-mount
nssm status rclone-mount
nssm restart rclone-mount
nssm remove rclone-mount

## gcp cloud run

Application Default Credentials (ADC) on GCP
When no other source of credentials is provided, rclone will fall back to Application Default Credentials. This is useful both when you already have configured authentication for your developer account, or in production when running on a Google compute host GitHubRclone.
This means on Cloud Run, Compute Engine, GKE, or any GCP service with an attached service account, rclone can automatically use the instance's service account credentials.
What the Config File Looks Like
Minimal Config (Using ADC):
ini[mygcs]
type = google cloud storage
bucket_policy_only = true

# kb

## daemon

--daemon
What it does: Runs rclone mount in background as a daemon process.
Practical impact:

Mount stays active after you close terminal
Terminal doesn't stay occupied
Process runs in background until explicitly unmounted

Example:
bash# Without --daemon:
rclone mount mygcs:bucket ./data
=> Terminal hangs, Ctrl+C unmounts

With --daemon:
rclone mount mygcs:bucket ./data --daemon
=> Returns immediately, you can keep working
=> Mount stays active until: fusermount -u ./data

# Finding Your Cache Location
bash# Check current cache directory
rclone config paths

This shows:
Config file: C:\Users\...\rclone.conf
Cache dir:   C:\Users\...\AppData\Local\rclone\vfs\
Temp dir:    C:\Users\...\AppData\Local\Temp\
Changing Cache Location
Yes, you can change it! Use the --cache-dir flag:
bash# Custom cache location
rclone mount mygcs:bucket D:\myrepo\data \
  --vfs-cache-mode writes \
  --cache-dir "D:\rclone-cache" \
  --daemon
Or set it globally in config:
bash# Edit rclone config
rclone config

Or manually edit the config file and add:
[global]
cache_dir = D:\rclone-cache

# user access

Option 1: Service Account Per User (Most Secure)Architecture:

Create a separate GCS service account for each user
Use IAM conditions to restrict access to specific bucket paths
Each user gets their own JSON key
Implementation:bash# 1. Create service account for user1
gcloud iam service-accounts create user1-storage \
  --display-name="User 1 Storage Access"

# 2. Create custom IAM role with path restrictions
gcloud iam roles create user1_restricted_access \
  --project=YOUR_PROJECT \
  --title="User 1 Restricted Access" \
  --permissions=storage.objects.get,storage.objects.create,storage.objects.delete,storage.objects.list

# 3. Grant access with IAM condition (path restriction)
gcloud storage buckets add-iam-policy-binding gs://YOUR_BUCKET \
  --member="serviceAccount:user1-storage@PROJECT.iam.gserviceaccount.com" \
  --role="projects/YOUR_PROJECT/roles/user1_restricted_access" \
  --condition='expression=resource.name.startsWith("projects/_/buckets/YOUR_BUCKET/objects/user1/"),title=user1-path-restriction'

# 4. Generate key for user
gcloud iam service-accounts keys create user1-key.json \
  --iam-account=user1-storage@PROJECT.iam.gserviceaccount.com