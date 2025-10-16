# requirements install
# oryxforge, d6tflow, adtiam gcs copy

# gcp deploy

cd api
gcloud run deploy oryx-forge-dev-20250823 --source . --region us-central1 --allow-unauthenticated  --set-env-vars GOOGLE_CLOUD_PROJECT=adt-dev-414714 --project=adt-dev-414714 --execution-environment=gen2   --add-volume='name=oryx-forge-api-data,type=cloud-storage,bucket=orxy-forge-datasets-dev' --add-volume-mount='volume=oryx-forge-api-data,mount-path=/mnt/data'
# checks 1) click on api link, see basic message 2) run utest/api20250908.py
# to delete need to delete both the service and Artifact Registry / Images for cloud-run-source-deploy
