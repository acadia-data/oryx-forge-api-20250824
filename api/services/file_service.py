import os
import pandas as pd
from typing import Dict, Any, Union
from supabase import Client
import pathlib


class FileService:
    """
    Service class for handling file operations and previews.
    """
    
    def __init__(self, supabase_client: Client, bucket_name: str = "data-source-files"):
        self.supabase_client = supabase_client
        self.bucket_name = bucket_name
    
    def get_data_source_record(self, fileid: str) -> Dict[str, Any]:
        """
        Retrieve data source record from Supabase.
        
        Args:
            fileid: The file ID to look up
            
        Returns:
            The data source record
            
        Raises:
            ValueError: If no data source is found
        """
        r = (
            self.supabase_client.table("data_sources")
            .select("*")
            .eq("id", fileid)
            .execute()
        )

        if not r.data:
            raise ValueError(f"No data source found for fileid: {fileid}")
        
        return r.data[0]
    
    def download_file(self, source_record) -> str:
        """
        Download file from Supabase storage.
        
        Args:
            fileid: The file ID to download
            data_dir: Directory to save the file
            
        Returns:
            Path to the downloaded file
        """

        fpath = f"data/supabase/{source_record['project_id']}/{source_record['id']}/{source_record['name']}"
        fpath = pathlib.Path(fpath)
        fpath.parent.mkdir(parents=True, exist_ok=True)

        # Download the file content
        file_response = self.supabase_client.storage.from_(self.bucket_name).download(source_record['uri'])
        
        # Write the file to disk
        with open(fpath, "wb") as f:
            f.write(file_response)
        
        return fpath
    
    def read_file_preview(self, source_record: dict, file_path: str) -> Dict[str, Any]:
        """
        Read file and return preview data based on file type.
        
        Args:
            file_path: Path to the file to read
            file_type: Type of the file (csv, excel, parquet)
            
        Returns:
            Preview data dictionary
            
        Raises:
            ValueError: If file type is unsupported
        """
        file_type = source_record.get("type", "").lower()

        if file_type == "csv":
            df_data = pd.read_csv(file_path)
            return {"data": df_data.head(100)}
        elif file_type == "excel":
            # Read all sheets
            df_data = pd.read_excel(file_path, sheet_name=None)
            preview_data = {sheetname: df.head(100) for sheetname, df in df_data.items()}
            return preview_data

        elif file_type == "parquet":
            df_data = pd.read_parquet(file_path)
            return {"data": df_data.head(100)}
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
    
    def cleanup_file(self, file_path: str) -> None:
        """
        Remove temporary file from disk.
        
        Args:
            file_path: Path to the file to remove
        """
        if os.path.exists(file_path):
            os.remove(file_path)
    
    def preview_file(self, fileid: str) -> Dict[str, Any]:
        """
        Main method to preview a file from Supabase storage.
        
        Args:
            fileid: The file ID to preview
            
        Returns:
            Preview data dictionary
            
        Raises:
            ValueError: If file cannot be processed
        """

        file_path = None

        # Get the data source record
        source_record = self.get_data_source_record(fileid)

        # Download file
        file_path = self.download_file(source_record)
        
        # Read and return preview data
        return self.read_file_preview(source_record, file_path)
            
