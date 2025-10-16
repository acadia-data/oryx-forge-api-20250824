python -m build

gcloud storage cp dist/oryxforge-25.9.8-py3-none-any.whl gs://adt-devops-pypi/packages/  --project adt-dev-414714

# pip install https://storage.googleapis.com/adt-devops-pypi/packages/oryxforge-25.9.8-py3-none-any.whl

# d6tflow
gcloud storage cp dist/d6tflow-25.6.21-py3-none-any.whl gs://adt-devops-pypi/packages/  --project adt-dev-414714
