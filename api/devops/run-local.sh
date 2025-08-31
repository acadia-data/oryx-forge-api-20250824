uvicorn app:app --reload 

uv pip install -r requirements.txt
# has an issue with hardlinking, maybe poetry is better?
uv run uvicorn app:app --reload
uv run uvicorn app:app
