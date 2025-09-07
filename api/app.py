from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import pandas as pd
from supabase import create_client, Client

import adtiam
adtiam.load_creds('adt-llm')

# Initialize Supabase client
adtiam.load_creds('adt-db')
# cnxn_supabase = create_client(adtiam.creds['db']['supabase']['url'], adtiam.creds['db']['supabase']['key-public'])
cnxn_supabase = create_client(adtiam.creds['db']['supabase']['url'], adtiam.creds['db']['supabase']['key-admin'])


app = FastAPI(title="Oryx Forge API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=False, # can't be true with allow_origins*
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Exception handlers for proper error responses
@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    """Handle ValueError exceptions and return appropriate HTTP responses."""
    error_message = str(exc)
    
    if "No data source found" in error_message:
        raise HTTPException(status_code=404, detail=error_message)
    elif "Unsupported file type" in error_message:
        raise HTTPException(status_code=400, detail=error_message)
    else:
        raise HTTPException(status_code=400, detail=error_message)

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions and return 500 status with error details."""
    raise HTTPException(status_code=500, detail=f"Internal server error: {str(exc)}")

@app.get("/")
def read_root():
    """
    A simple root endpoint that returns a greeting.
    """
    return {"message": "Oryx Forge API"}

@app.get("/$env")
def get_environment_variable():
    """
    An endpoint to return all environment variables as a dictionary.
    """
    return dict(os.environ)

@app.get("/utest-llm")
def get_llm():

    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(api_key=adtiam.creds['llm']['openai'],model="gpt-4.1-mini-2025-04-14", temperature=0)

    r = llm.invoke("What is the capital of the UAE?")

    return r

from pydantic import BaseModel

class PromptRequest(BaseModel):
    prompt: str

class BaseFileRequest(BaseModel):
    user_owner: str
    project_id: str
    data_source_id: str

class FilePreviewRequest(BaseFileRequest):
    pass

class FileImportRequest(BaseFileRequest):
    settings_load: dict
    settings_save: dict

@app.post("/llm")
def get_llm_stream(request: PromptRequest):
    """
    A streaming endpoint that takes a prompt and returns a streaming LLM response.
    """
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(api_key=adtiam.creds['llm']['openai'], model="gpt-4.1-mini-2025-04-14", temperature=0, streaming=True)

    def generate_stream():
        for chunk in llm.stream(request.prompt):
            if chunk.content:
                yield f"data: {chunk.content}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate_stream(), media_type="text/plain")

@app.post("/llm-openai")
def get_llm_native_stream(request: PromptRequest):
    """
    Native OpenAI streaming endpoint using openai library directly.
    """
    import openai
    
    client = openai.OpenAI(api_key=adtiam.creds['llm']['openai'])
    
    def generate_stream():
        stream = client.chat.completions.create(
            model="gpt-4.1-mini-2025-04-14",
            messages=[{"role": "user", "content": request.prompt}],
            temperature=0,
            stream=True
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield f"data: {chunk.choices[0].delta.content}\n\n"
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(generate_stream(), media_type="text/plain")

from services.file_service import FileService


def dataframe_to_spreadsheet_format(df):
    # Handle NaN values
    df_clean = df.fillna('')  # or df.fillna(None) for null values

    return {
        "headers": df_clean.columns.tolist(),
        "data": df_clean.values.tolist()
    }


@app.post("/files/preview")
def preview_file(request: FilePreviewRequest):
    """
    Preview a file from Supabase storage based on data_source_id.
    Downloads the file, reads it with pandas, and returns preview data.
    """
    # Create file service instance with common parameters
    file_service = FileService(cnxn_supabase, request.user_owner, request.project_id, request.data_source_id)
    
    # Use service to preview data source - let exceptions bubble up to FastAPI
    preview_data = file_service.preview_data_source()
    preview_data = {k: dataframe_to_spreadsheet_format(df) for k, df in preview_data.items()}

    return preview_data


@app.post("/files/import")
def import_file(request: FileImportRequest):
    """
    Import a file from Supabase storage to Google Cloud Storage and create records.
    Downloads the file, processes selected sheets, saves to GCS, and creates/updates Supabase records.
    """
    # Create file service instance with common parameters
    file_service = FileService(cnxn_supabase, request.user_owner, request.project_id, request.data_source_id)
    
    # Extract settings
    settings_save = request.settings_save
    create_new_dataset = settings_save.get("createNewDataset", False)
    dataset_name = settings_save.get("datasetName") if create_new_dataset else None
    
    if not create_new_dataset and dataset_name is None:
        raise HTTPException(status_code=400, detail="Dataset name is required when not creating a new dataset")
    
    selected_sheets = settings_save.get("selectedSheets", {})
    
    if not selected_sheets:
        raise HTTPException(status_code=400, detail="No sheets selected for import")
    
    # Use service to import file
    result = file_service.import_file(
        selected_sheets=selected_sheets,
        dataset_name=dataset_name
    )
    
    return result

